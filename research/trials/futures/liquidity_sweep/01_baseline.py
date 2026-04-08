"""Baseline trial for the bear NY_PRE/AFTER 1H sweep strategy.

Runs the legacy backtest logic through the project adapter layer so the trial
lives under research/ with the existing structure.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.standards import CALMAR, MAX_DRAWDOWN_LIMIT, PROFIT_FACTOR, SHARPE
from research.graph_export import write_baseline_csv
from strategies.adapters.liquidity_sweep_adapter import (
    load_data_from_store,
    run_with_data,
)

# Defaults aligned with the explained profile file.
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


RISK_PER_TRADE = 0.01


def _to_builtin(value):
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _proxy_equity_from_r(trades_df: pd.DataFrame, risk_per_trade: float = RISK_PER_TRADE) -> pd.Series:
    """Build a normalized equity curve from per-trade R multiples."""
    if trades_df.empty:
        return pd.Series(dtype=float)
    returns = trades_df["pnl_r"].astype(float) * float(risk_per_trade)
    equity = (1.0 + returns).cumprod() * 100_000
    equity.index = pd.to_datetime(trades_df["entry_time"])
    return equity


def _legacy_result_to_row(result: dict, config: dict) -> dict:
    m = result["metrics"]
    n = int(m.get("sample_size", 0) or 0)
    trades_df = result.get("trades_df", pd.DataFrame())
    equity = _proxy_equity_from_r(trades_df)
    proxy = summary(equity) if not equity.empty else {"return": float("nan"), "calmar": float("nan"), "max_drawdown": float("nan")}

    # Legacy engine reports R-based metrics; keep them explicit while also
    # providing evaluator-compatible columns for standardized trial output.
    clean_cfg = {
        "target_r": _to_builtin(config.get("target_r")),
        "max_hold_bars": _to_builtin(config.get("max_hold_bars")),
        "wick_mode": _to_builtin(config.get("wick_mode")),
        "chain_mode": _to_builtin(config.get("chain_mode")),
    }
    return {
        **clean_cfg,
        "sample_size": n,
        "total_r": _to_builtin(m.get("total_r")),
        "avg_r_per_trade": _to_builtin(m.get("avg_r_per_trade")),
        "breakeven_win_rate": _to_builtin(m.get("breakeven_win_rate")),
        "sharpe": _to_builtin(m.get("sharpe", float("nan"))),
        "profit_factor": _to_builtin(m.get("profit_factor", float("nan"))),
        "win_rate": _to_builtin(m.get("win_rate", float("nan"))),
        "n_trades": n,
        "return": _to_builtin(proxy.get("return", float("nan"))),
        "max_drawdown": _to_builtin(proxy.get("max_drawdown", float("nan"))),
        "calmar": _to_builtin(proxy.get("calmar", float("nan"))),
        "gain": float("nan"),
        "fees": float("nan"),
        "first_trade_ts": pd.Timestamp(trades_df["entry_time"].min()).isoformat() if not trades_df.empty else None,
        "last_trade_ts": pd.Timestamp(trades_df["entry_time"].max()).isoformat() if not trades_df.empty else None,
    }


def _exposure_normalized_metrics(
    n_trades: int,
    max_hold_bars_5m: int,
    total_hours: int,
    strategy_return: float,
    bh_return: float,
) -> dict:
    max_hours_in_market = n_trades * max_hold_bars_5m * (5 / 60)
    exposure_frac = (max_hours_in_market / total_hours) if total_hours > 0 else float("nan")
    bh_exposure_return = bh_return * exposure_frac
    outperformance_x = (
        (strategy_return / bh_exposure_return)
        if bh_exposure_return not in (0, float("nan")) and bh_exposure_return == bh_exposure_return
        else float("nan")
    )
    return {
        "strategy_return": strategy_return,
        "bh_exposure_return": bh_exposure_return,
        "outperformance_x": outperformance_x,
        "max_hours_in_market": max_hours_in_market,
        "total_hours": total_hours,
        "exposure_frac": exposure_frac,
    }


def _print_exposure_normalized(metrics: dict) -> None:
    print("\n========== EXPOSURE-NORMALIZED BENCHMARK ==========")
    print(f"Strategy return: {metrics['strategy_return']:.2%}")
    print(f"BH normalized to same exposure: {metrics['bh_exposure_return']:.2%}")
    print(f"Strategy outperformance: {metrics['outperformance_x']:.2f}x")
    print(
        "Max time in market: "
        f"{metrics['exposure_frac']:.2%} "
        f"({metrics['max_hours_in_market']:.0f}h of {metrics['total_hours']:,}h)"
    )


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
    """Write a simple HTML artifact with metadata, BH stats, and results table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_html = pd.DataFrame(
        [{"field": k, "value": v} for k, v in metadata.items()]
    ).to_html(index=False, border=0, classes="table")
    bh_html = pd.DataFrame([bh]).to_html(index=False, border=0, classes="table")
    exposure_html = pd.DataFrame([exposure_metrics]).to_html(index=False, border=0, classes="table")
    if tier_assessment.get("rows"):
        tier_html = pd.DataFrame(tier_assessment["rows"]).to_html(index=False, border=0, classes="table")
    else:
        tier_html = "<p>No valid results.</p>"

    if results.empty:
        results_html = "<p>No valid results.</p>"
    else:
        results_html = results.to_html(index=False, border=0, classes="table")

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Liquidity Sweep Report</title>
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
  <h1>Liquidity Sweep Trial Report</h1>
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




def main() -> None:
    ap = argparse.ArgumentParser(description="Liquidity sweep baseline trial")
    ap.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Write all artifacts here (default: research/results/futures/liquidity_sweep/)",
    )
    args = ap.parse_args()
    _default_out = ROOT / "research" / "results" / "futures" / "liquidity_sweep"
    _out_dir = Path(args.output_dir) if args.output_dir else _default_out
    _out_dir.mkdir(parents=True, exist_ok=True)

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
        "strategy": "liquidity_sweep",
        "symbol": "CL_continuous_1H (+ CL/MES/MNQ 5min)",
        "freq": "1H",
        "leverage": f"legacy R-model ({RISK_PER_TRADE:.1%} risk proxy)",
        "fees": "embedded in legacy result",
        "time_stop": CONFIG_OVERRIDES["max_hold_bars"],
        "data_span": data_span,
    }

    rows = []
    if int(result["metrics"].get("sample_size", 0) or 0) > 0:
        rows.append(_legacy_result_to_row(result, CONFIG_OVERRIDES))
    results = pd.DataFrame(rows)

    if not results.empty:
        results["backtest_start"] = cl1h.index.min().isoformat()
        results["backtest_end"] = cl1h.index.max().isoformat()
        results = evaluate(results, bh)
    report(results, bh, metadata, top_n=1, full_n=1)

    if not results.empty:
        row = results.iloc[0]
        exposure_metrics = _exposure_normalized_metrics(
            n_trades=int(row["n_trades"]),
            max_hold_bars_5m=int(CONFIG_OVERRIDES["max_hold_bars"]),
            total_hours=int(len(cl1h)),
            strategy_return=float(row["return"]),
            bh_return=float(bh["return"]),
        )
    else:
        exposure_metrics = _exposure_normalized_metrics(
            n_trades=0,
            max_hold_bars_5m=int(CONFIG_OVERRIDES["max_hold_bars"]),
            total_hours=int(len(cl1h)),
            strategy_return=float("nan"),
            bh_return=float(bh["return"]),
        )

    _print_exposure_normalized(exposure_metrics)
    tier_assessment = _tier_assessment_payload(results, bh)

    html_path = _out_dir / "index.html"
    _write_index_html(metadata, bh, results, tier_assessment, exposure_metrics, html_path)
    print(f"\nHTML report written: {html_path}")

    csv_path = _out_dir / "baseline_results.csv"
    if not results.empty:
        write_baseline_csv(
            results,
            output_path=csv_path,
            instrument="CL",
            timeframe="1H",
            direction="bear",
            logic_type="liquidity-sweep",
        )
        print(f"Baseline CSV written: {csv_path}")
    else:
        print("Baseline CSV not written (no valid results).")


if __name__ == "__main__":
    main()
