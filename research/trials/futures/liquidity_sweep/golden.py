"""Golden liquidity sweep strategy with rdist volatility-targeted position sizing.

This is the baseline strategy with position sizing optimized to scale risk inversely
with r_dist (reward-to-risk distance). Larger r_dist = smaller position size, smaller
r_dist = larger position size (within bounds).

Entry/exit logic unchanged from baseline; only sizing differs.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.standards import CALMAR, MAX_DRAWDOWN_LIMIT, PROFIT_FACTOR, SHARPE
from research.trials.futures.liquidity_sweep.position_sizing import (
    build_sized_equity,
    exposure_normalized,
)
from strategies.adapters.liquidity_sweep_adapter import load_data_from_store, run_with_data

# Baseline config (entry/exit rules unchanged)
CONFIG_OVERRIDES = {
    "target_r": 1.25,
    "max_hold_bars": 24,
    "wick_mode": "exclude_q2",
    "chain_mode": "no_smt_in_chain",
    "partial_exit_r": 0.0,
    "stall_bars": 0,
    "allowed_sessions": ["NY_PRE", "AFTER"],
    "allowed_dir": ["BEAR"],
}

# Golden sizing: rdist volatility targeting
SIZING_CONFIG = {
    "mode": "rdist_vol_target",
    "base_risk": 0.0100,
    "min_risk": 0.0025,
    "max_risk": 0.0200,
}


def _to_builtin(value):
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _tier_flag(value: float, thresholds: dict, hard_limit: float | None = None) -> str:
    if hard_limit is not None and value < hard_limit:
        return "FAIL"
    if value >= thresholds.get("institutional", float("inf")):
        return "INSTITUTIONAL"
    if value >= thresholds.get("professional", float("inf")):
        return "PROFESSIONAL"
    if value >= thresholds.get("pass", float("inf")):
        return "PASS"
    return "FAIL"


def _tier_assessment_payload(results: pd.DataFrame, bh: dict) -> dict:
    if results.empty:
        return {"title": "No valid results", "rows": []}

    best = results.iloc[0]
    sharpe_flag = _tier_flag(float(best["sharpe"]), SHARPE)
    pf_flag = _tier_flag(float(best["profit_factor"]), PROFIT_FACTOR)
    calmar_flag = _tier_flag(float(best["calmar"]), CALMAR)
    dd_flag = "PASS" if float(best["max_drawdown"]) >= MAX_DRAWDOWN_LIMIT else "FAIL"
    beat_bh = "YES" if bool(best.get("beat_bh", False)) else "NO"
    delta = float(best["sharpe"]) - float(bh["sharpe"])

    return {
        "title": str(best.get("tier", "—")).upper(),
        "rows": [
            {
                "metric": "Sharpe",
                "value": f"{float(best['sharpe']):.3f}",
                "status": f"{sharpe_flag} (min {SHARPE['pass']})",
            },
            {
                "metric": "Profit Factor",
                "value": f"{float(best['profit_factor']):.3f}",
                "status": f"{pf_flag} (min {PROFIT_FACTOR['pass']})",
            },
            {
                "metric": "Calmar",
                "value": f"{float(best['calmar']):.3f}",
                "status": f"{calmar_flag} (min {CALMAR['pass']})",
            },
            {
                "metric": "Max Drawdown",
                "value": f"{float(best['max_drawdown']):+.2%}",
                "status": f"{dd_flag} (limit {MAX_DRAWDOWN_LIMIT:.0%})",
            },
            {
                "metric": "Beat BH",
                "value": beat_bh,
                "status": f"{delta:+.3f} vs BH sharpe {float(bh['sharpe']):.3f}",
            },
        ],
    }


def _write_index_html(
    metadata: dict,
    bh: dict,
    results: pd.DataFrame,
    tier_assessment: dict,
    exposure_metrics: dict,
    output_path: Path,
) -> None:
    """Write golden strategy report to HTML."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_html = pd.DataFrame(
        [{"field": k, "value": v} for k, v in metadata.items()]
    ).to_html(index=False, border=0, classes="table")
    bh_html = pd.DataFrame([bh]).to_html(index=False, border=0, classes="table")
    if tier_assessment.get("rows"):
        tier_html = pd.DataFrame(tier_assessment["rows"]).to_html(index=False, border=0, classes="table")
    else:
        tier_html = "<p>No valid results.</p>"

    # Format exposure-normalized benchmark as comparison card
    strategy_ret = float(results.iloc[0]["return"]) if not results.empty else float("nan")
    bh_exp_ret = float(exposure_metrics["bh_exposure_return"])
    outperf_x = float(exposure_metrics["outperformance_x"])
    exposure_frac = float(exposure_metrics["exposure_frac"])
    exposure_html = f"""
    <div style="background: #f0f8ff; padding: 16px; border-left: 4px solid #0066cc; margin-bottom: 12px;">
      <p style="margin: 0 0 8px; font-size: 14px; color: #666;">
        Max time in market: <strong>{exposure_frac:.2%}</strong> ({exposure_metrics['max_hours_in_market']:.0f}h of {exposure_metrics['total_hours']:.0f}h)
      </p>
      <p style="margin: 0 0 12px; font-size: 16px; font-weight: bold; color: #333;">
        Strategy: <span style="color: #0066cc;">{strategy_ret:.2%}</span> &nbsp;&nbsp;
        BH (normalized): <span style="color: #999;">{bh_exp_ret:.2%}</span>
      </p>
      <p style="margin: 0; font-size: 18px; font-weight: bold; color: #008000;">
        Outperformance: {outperf_x:.2f}x
      </p>
    </div>
    """

    if results.empty:
        results_html = "<p>No valid results.</p>"
    else:
        results_html = results.to_html(index=False, border=0, classes="table")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Liquidity Sweep Golden Strategy</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin-bottom: 24px; }}
    .table {{ border-collapse: collapse; width: 100%; }}
    .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    .table th {{ background: #f7f7f7; }}
  </style>
</head>
<body>
  <h1>Liquidity Sweep Golden Strategy</h1>
  <p><strong>Position sizing:</strong> rdist volatility targeting — scales risk inversely with reward-to-risk distance.</p>
  <section>
    <h2>Metadata</h2>
    {metadata_html}
  </section>
  <section>
    <h2>Buy and Hold</h2>
    {bh_html}
  </section>
  <section>
    <h2>Tier Assessment (best result)</h2>
    <p><strong>{tier_assessment.get('title', '—')}</strong></p>
    {tier_html}
  </section>
  <section>
    <h2>Exposure-Normalized Benchmark</h2>
    {exposure_html}
  </section>
  <section>
    <h2>Results</h2>
    {results_html}
  </section>
</body>
</html>
"""
    output_path.write_text(html)


def _write_champion_md(results: pd.DataFrame, n_trades: int, output_path: Path) -> bool:
    """Write a champion_md artifact for qw record ingestion.

    The filename encodes the strategy for parser inference:
    cl_bear_liquidity_sweep_1h_golden_champion → instrument=CL, direction=bear,
    logic_type=liquidity-sweep, timeframe=1H.

    Fields that require human or OOS validation (oos_status, fragilities) are
    populated with explicit placeholder defaults so the Champion model validates.
    """
    if results.empty:
        return False

    row = results.iloc[0]
    freeze_date = date.today().isoformat()

    sharpe = float(row.get("sharpe", float("nan")))
    profit_factor = float(row.get("profit_factor", float("nan")))
    win_rate = float(row.get("win_rate", float("nan")))
    max_drawdown = float(row.get("max_drawdown", float("nan")))
    calmar = float(row.get("calmar", float("nan")))
    ret = float(row.get("return", float("nan")))
    sizing_mode = str(row.get("sizing_mode", SIZING_CONFIG["mode"]))
    tier = str(row.get("tier", "")).lower() or "unrated"

    content = f"""# CL Bear Liquidity Sweep 1H — Golden Champion

**Status**: Candidate (pending OOS validation)
**Freeze Date**: {freeze_date}

---

## Config (Champion)

- Instrument: CL
- Direction: bear
- Sweep timeframe: 1H
- target_r: {CONFIG_OVERRIDES["target_r"]}
- max_hold_bars: {CONFIG_OVERRIDES["max_hold_bars"]}
- wick_mode: {CONFIG_OVERRIDES["wick_mode"]}
- chain_mode: {CONFIG_OVERRIDES["chain_mode"]}
- allowed_sessions: {", ".join(CONFIG_OVERRIDES["allowed_sessions"])}
- allowed_dir: {", ".join(CONFIG_OVERRIDES["allowed_dir"])}
- sizing_mode: {sizing_mode}

---

## IS Metrics (Champion)

- Sample size: {n_trades}
- Total Trades: {n_trades}
- Sharpe: {sharpe:.6f}
- Profit factor: {profit_factor:.6f}
- Win rate: {win_rate:.6f}
- Max drawdown: {max_drawdown:.6f}
- Calmar: {calmar:.6f}
- Return: {ret:.6f}
- Tier: {tier}

Source: `research/results/futures/liquidity_sweep/golden_results.csv`

---

## Known Fragilities

1. No OOS validation performed — auto-generated champion draft.
2. Single instrument, single direction (CL bear) — regime sensitivity unknown.
3. Position sizing mode ({sizing_mode}) scales risk with r_dist; degradation under low-volatility regimes is untested.
4. Win rate sensitivity: small reductions in average winner size can break expectancy.

---

## OOS Command (Champion)

```zsh
# Run OOS after reviewing IS metrics above.
# Add --pivot-from <run_id> once the baseline run_id is known.
python research/trials/futures/liquidity_sweep/golden.py \\
  --start-date <oos_start> \\
  --end-date <oos_end>
```
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return True


def _write_golden_csv(results: pd.DataFrame, output_path: Path) -> bool:
    """Write a graph-ingestable baseline CSV for the golden strategy result."""
    if results.empty:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export = results.copy()

    # Required strategy metadata for qws_graph CSV parser.
    export["instrument"] = "CL"
    export["timeframe"] = "1H"
    export["direction"] = "bear"
    export["logic_type"] = "liquidity-sweep"

    # Map trial columns to parser expectations.
    export["total_trades"] = export["n_trades"]
    export["win_rate"] = export["win_rate"]

    keep_cols = [
        "instrument",
        "timeframe",
        "direction",
        "logic_type",
        "sizing_mode",
        "sharpe",
        "profit_factor",
        "win_rate",
        "max_drawdown",
        "total_trades",
        "return",
        "calmar",
    ]
    export = export[[c for c in keep_cols if c in export.columns]]
    export.to_csv(output_path, index=False)
    return True


def main() -> None:
    data = load_data_from_store()
    result = run_with_data(data=data, config_overrides=CONFIG_OVERRIDES)

    cl1h = data["cl1h"]
    bh_equity = cl1h["close"] / cl1h["close"].iloc[0] * 100_000
    bh = summary(bh_equity)

    data_span = (
        f"{cl1h.index.min().strftime('%Y-%m-%d %H:%M')} -> "
        f"{cl1h.index.max().strftime('%Y-%m-%d %H:%M')} "
        f"({len(cl1h):,} 1H bars)"
    )
    metadata = {
        "strategy": "liquidity_sweep_golden",
        "position_sizing": "rdist_vol_target",
        "symbol": "CL_continuous_1H (+ CL/MES/MNQ 5min)",
        "freq": "1H",
        "data_span": data_span,
    }

    # Replay baseline trades with golden sizing
    trades = result.get("trades_df", pd.DataFrame())
    if trades.empty:
        print("No trades from baseline config; cannot apply golden sizing.")
        return

    sized_equity = build_sized_equity(
        trades,
        mode=SIZING_CONFIG["mode"],
        base_risk=SIZING_CONFIG["base_risk"],
        min_risk=SIZING_CONFIG["min_risk"],
        max_risk=SIZING_CONFIG["max_risk"],
    )

    # Evaluate the sized results
    metrics = summary(sized_equity["equity"], sized_equity["trade_return"])
    exposure = exposure_normalized(
        strategy_return=float(metrics["return"]),
        bh_return=float(bh["return"]),
        n_trades=len(trades),
        max_hold_bars_5m=int(CONFIG_OVERRIDES["max_hold_bars"]),
        total_hours=int(len(cl1h)),
    )

    # Build single-row results DataFrame for evaluator compatibility
    row = {
        "target_r": _to_builtin(CONFIG_OVERRIDES["target_r"]),
        "max_hold_bars": _to_builtin(CONFIG_OVERRIDES["max_hold_bars"]),
        "wick_mode": _to_builtin(CONFIG_OVERRIDES["wick_mode"]),
        "chain_mode": _to_builtin(CONFIG_OVERRIDES["chain_mode"]),
        "sizing_mode": SIZING_CONFIG["mode"],
        "avg_risk_pct": float(sized_equity["risk_pct"].mean()),
        "sample_size": len(trades),
        "sharpe": float(metrics["sharpe"]),
        "profit_factor": float(metrics.get("profit_factor", float("nan"))),
        "win_rate": float(metrics["win_rate"]),
        "calmar": float(metrics["calmar"]),
        "max_drawdown": float(metrics["max_drawdown"]),
        "return": float(metrics["return"]),
        "n_trades": len(trades),
        "gain": float("nan"),
        "fees": float("nan"),
        **exposure,
    }
    results = pd.DataFrame([row])
    results = evaluate(results, bh)

    # For reporting, use exposure-normalized BH return so delta shows true outperformance
    bh_exposure_adjusted = {**bh, "return": exposure["bh_exposure_return"]}

    print("\n========== GOLDEN STRATEGY ==========")
    print(f"Strategy return: {metrics['return']:.2%}")
    print(f"BH normalized to same exposure: {exposure['bh_exposure_return']:.2%}")
    print(f"Strategy outperformance: {exposure['outperformance_x']:.2f}x")
    print(f"Avg position size: {float(sized_equity['risk_pct'].mean()):.2%}")
    print(f"Sharpe: {metrics['sharpe']:.3f}")
    print(f"Calmar: {metrics['calmar']:.3f}")
    print(f"Max drawdown: {metrics['max_drawdown']:.2%}")

    report(results, bh_exposure_adjusted, metadata, top_n=1, full_n=1)

    tier_assessment = _tier_assessment_payload(results, bh)
    html_path = ROOT / "research" / "results" / "futures" / "liquidity_sweep" / "golden.html"
    _write_index_html(metadata, bh, results, tier_assessment, exposure, html_path)
    print(f"\nHTML report written: {html_path}")

    csv_path = ROOT / "research" / "results" / "futures" / "liquidity_sweep" / "golden_results.csv"
    if _write_golden_csv(results, csv_path):
        print(f"Golden strategy CSV written: {csv_path}")
    else:
        print("Golden strategy CSV not written (no valid results).")

    champion_md_path = (
        ROOT / "research" / "results" / "futures" / "liquidity_sweep"
        / "cl_bear_liquidity_sweep_1h_golden_champion.md"
    )
    if _write_champion_md(results, len(trades), champion_md_path):
        print(f"Champion markdown written: {champion_md_path}")
    else:
        print("Champion markdown not written (no valid results).")


if __name__ == "__main__":
    main()





