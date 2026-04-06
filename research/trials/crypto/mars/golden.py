"""BTC Bull MARS 1D — Golden Strategy.

MARS (Momentum + Allocation + Rebalancing + Screening) long-only on BTC/USD daily bars.

Entry: momentum > 0, close > SMA(trend_period), ATR/close < vol_threshold
Exit:  momentum reversal (signal goes to -1) OR time_stop bars elapsed
Direction: bull (long-only)

Produces two graph-ingestable artifacts:
  - btc_bull_mars_1d_golden_results.csv    → qw record --kind baseline_csv
  - btc_bull_mars_1d_golden_champion.md    → qw record --kind champion_md
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.store import get_store
from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.standards import CALMAR, MAX_DRAWDOWN_LIMIT, PROFIT_FACTOR, SHARPE
from strategies.mars import MARS

# ── Fixed golden config ────────────────────────────────────────────────────────
CONFIG: dict = {
    "mom_period": 20,
    "trend_period": 50,
    "atr_period": 14,
    "vol_threshold": 0.05,
}

BACKTEST_CONFIG: dict = {
    "init_cash": 100_000.0,
    "leverage": 3.0,
    "time_stop": 20,    # force exit after 20 bars if no reversal
    "fees": 0.001,      # 0.1% Alpaca crypto taker per side
}

_OUTPUT_DIR = ROOT / "research" / "results" / "crypto" / "mars"
_CSV_PATH = _OUTPUT_DIR / "btc_bull_mars_1d_golden_results.csv"
_CHAMPION_MD_PATH = _OUTPUT_DIR / "btc_bull_mars_1d_golden_champion.md"
_HTML_PATH = _OUTPUT_DIR / "btc_bull_mars_1d_golden.html"


# ── Backtest ──────────────────────────────────────────────────────────────────

def _run_backtest(
    signals: pd.Series,
    bars: pd.DataFrame,
    init_cash: float,
    leverage: float,
    fees: float,
    time_stop: int,
) -> tuple[pd.Series, pd.Series]:
    """Pure-pandas long-only backtest.

    Entry at close of signal bar; exit at close of reversal/time-stop bar.
    One position at a time — ignores new entry signals while in a trade.

    Returns
    -------
    equity : pd.Series
        Mark-to-market equity curve indexed same as bars.
    trade_pnl : pd.Series
        Gross dollar PnL per completed trade (for win_rate/profit_factor).
    """
    close = bars["close"].values
    sig = signals.values
    n = len(close)

    equity = np.empty(n, dtype=float)
    equity[0] = init_cash
    trade_pnl: list[float] = []

    cash = float(init_cash)
    in_trade = False
    entry_idx = 0
    entry_price = 0.0

    for i in range(1, n):
        if in_trade:
            # Mark equity to market on each bar
            pct = close[i] / close[i - 1] - 1.0
            equity[i] = equity[i - 1] * (1.0 + pct * leverage)

            bars_held = i - entry_idx
            reversal = sig[i] == -1

            if reversal or bars_held >= time_stop:
                exit_price = close[i]
                gross_pct = (exit_price / entry_price - 1.0) * leverage
                net_pct = gross_pct - fees  # exit fee (entry fee taken at open)
                pnl_dollar = net_pct * cash
                trade_pnl.append(pnl_dollar)

                cash = equity[i] * (1.0 - fees)
                equity[i] = cash
                in_trade = False
        else:
            equity[i] = cash

        if not in_trade and sig[i] == 1:
            in_trade = True
            entry_idx = i
            entry_price = close[i]
            cash = cash * (1.0 - fees)  # entry fee
            equity[i] = cash

    # Force-close open position at end of data
    if in_trade:
        exit_price = close[-1]
        gross_pct = (exit_price / entry_price - 1.0) * leverage
        net_pct = gross_pct - fees
        trade_pnl.append(net_pct * cash)

    equity_series = pd.Series(equity, index=bars.index)
    return equity_series, pd.Series(trade_pnl)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Artifact writers ──────────────────────────────────────────────────────────

def _write_champion_md(results: pd.DataFrame, n_trades: int, output_path: Path) -> bool:
    """Write champion_md artifact for qw record ingestion.

    Filename encodes strategy for parser inference:
    btc_bull_mars_1d_golden_champion → instrument=BTC, direction=bull,
    logic_type=mars, timeframe=1D.
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
    tier = str(row.get("tier", "")).lower() or "unrated"

    content = f"""# BTC Bull MARS 1D — Golden Champion

**Status**: Candidate (pending OOS validation)
**Freeze Date**: {freeze_date}

---

## Config (Champion)

- Instrument: BTC
- Direction: bull
- Timeframe: 1D
- Logic type: mars
- mom_period: {CONFIG["mom_period"]}
- trend_period: {CONFIG["trend_period"]}
- atr_period: {CONFIG["atr_period"]}
- vol_threshold: {CONFIG["vol_threshold"]}
- leverage: {BACKTEST_CONFIG["leverage"]}
- time_stop: {BACKTEST_CONFIG["time_stop"]}

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

Source: `research/results/crypto/mars/btc_bull_mars_1d_golden_results.csv`

---

## Known Fragilities

1. No OOS validation performed — auto-generated champion draft.
2. Single asset (BTC), long-only — short-side edge not captured.
3. Momentum strategy is regime-dependent; prolonged bear markets suppress entries and produce flat equity.
4. Volatility filter (vol_threshold={CONFIG["vol_threshold"]}) may under-trade during high-volatility trending regimes.
5. 2-year IS window (2024-03-28 to 2026-03-27) — includes a sustained bull run; OOS in a bear regime required before promotion.

---

## OOS Command (Champion)

```zsh
# Run OOS after reviewing IS metrics above.
# Add --pivot-from <run_id> once the baseline run_id is known.
python research/trials/crypto/mars/golden.py \\
  --start-date <oos_start> \\
  --end-date <oos_end>
```
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return True


def _write_golden_csv(results: pd.DataFrame, output_path: Path) -> bool:
    """Write baseline_csv artifact for qw record ingestion."""
    if results.empty:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export = results.copy()

    export["instrument"] = "BTC"
    export["timeframe"] = "1D"
    export["direction"] = "bull"
    export["logic_type"] = "mars"
    export["total_trades"] = export["n_trades"]

    keep_cols = [
        "instrument", "timeframe", "direction", "logic_type",
        "mom_period", "trend_period", "atr_period", "vol_threshold",
        "sharpe", "profit_factor", "win_rate", "max_drawdown",
        "total_trades", "return", "calmar",
    ]
    export = export[[c for c in keep_cols if c in export.columns]]
    export.to_csv(output_path, index=False)
    return True


def _write_html(
    metadata: dict,
    bh: dict,
    results: pd.DataFrame,
    tier_assessment: dict,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_html = pd.DataFrame(
        [{"field": k, "value": v} for k, v in metadata.items()]
    ).to_html(index=False, border=0, classes="table")
    bh_html = pd.DataFrame([bh]).to_html(index=False, border=0, classes="table")
    tier_html = (
        pd.DataFrame(tier_assessment["rows"]).to_html(index=False, border=0, classes="table")
        if tier_assessment.get("rows")
        else "<p>No valid results.</p>"
    )
    results_html = (
        results.to_html(index=False, border=0, classes="table")
        if not results.empty
        else "<p>No valid results.</p>"
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BTC Bull MARS 1D — Golden Strategy</title>
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
  <h1>BTC Bull MARS 1D — Golden Strategy</h1>
  <p><strong>Strategy:</strong> Momentum + trend filter + volatility screen. Long-only on daily BTC.</p>
  <section><h2>Metadata</h2>{metadata_html}</section>
  <section><h2>Buy and Hold</h2>{bh_html}</section>
  <section>
    <h2>Tier Assessment</h2>
    <p><strong>{tier_assessment.get("title", "—")}</strong></p>
    {tier_html}
  </section>
  <section><h2>Results</h2>{results_html}</section>
</body>
</html>"""
    output_path.write_text(html)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="BTC Bull MARS 1D golden strategy trial")
    ap.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Write all artifacts here (default: research/results/crypto/mars/)",
    )
    args = ap.parse_args()
    _out_dir = Path(args.output_dir) if args.output_dir else _OUTPUT_DIR
    _out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = _out_dir / "btc_bull_mars_1d_golden_results.csv"
    champion_md_path = _out_dir / "btc_bull_mars_1d_golden_champion.md"
    html_path = _out_dir / "btc_bull_mars_1d_golden.html"

    bars = get_store().read_bars("crypto", "BTC/USD_1D")

    bh_equity = bars["close"] / bars["close"].iloc[0] * BACKTEST_CONFIG["init_cash"]
    bh = summary(bh_equity)

    data_span = (
        f"{bars.index.min().strftime('%Y-%m-%d')} -> "
        f"{bars.index.max().strftime('%Y-%m-%d')} "
        f"({len(bars):,} daily bars)"
    )
    metadata = {
        "strategy": "btc_bull_mars_1d_golden",
        "symbol": "BTC/USD_1D",
        "freq": "1D",
        "mom_period": CONFIG["mom_period"],
        "trend_period": CONFIG["trend_period"],
        "leverage": BACKTEST_CONFIG["leverage"],
        "data_span": data_span,
    }

    strategy = MARS(**CONFIG)
    signals = strategy.generate_signals(bars)

    equity, trade_pnl = _run_backtest(
        signals,
        bars,
        init_cash=BACKTEST_CONFIG["init_cash"],
        leverage=BACKTEST_CONFIG["leverage"],
        fees=BACKTEST_CONFIG["fees"],
        time_stop=BACKTEST_CONFIG["time_stop"],
    )

    n_trades = len(trade_pnl)
    if n_trades < 5:
        print(f"Only {n_trades} trades — insufficient for evaluation. Adjust CONFIG params.")
        return

    metrics = summary(equity, trade_pnl)

    print("\n========== BTC BULL MARS 1D GOLDEN ==========")
    print(f"Trades:        {n_trades}")
    print(f"Return:        {metrics['return']:.2%}")
    print(f"BH return:     {bh['return']:.2%}")
    print(f"Sharpe:        {metrics['sharpe']:.3f}  (BH: {bh['sharpe']:.3f})")
    print(f"Calmar:        {metrics['calmar']:.3f}")
    print(f"Max drawdown:  {metrics['max_drawdown']:.2%}")
    print(f"Win rate:      {metrics.get('win_rate', float('nan')):.2%}")
    print(f"Profit factor: {metrics.get('profit_factor', float('nan')):.3f}")

    gain = metrics["return"] * BACKTEST_CONFIG["init_cash"]
    fees_dollar = n_trades * 2 * BACKTEST_CONFIG["fees"] * BACKTEST_CONFIG["init_cash"]

    row = {
        **CONFIG,
        **metrics,
        "n_trades": n_trades,
        "gain": round(gain, 2),
        "fees": round(fees_dollar, 2),
    }
    results = pd.DataFrame([row])
    results = evaluate(results, bh)

    tier_assessment = _tier_assessment_payload(results, bh)
    report(results, bh, metadata, top_n=1, full_n=1)

    _write_html(metadata, bh, results, tier_assessment, html_path)
    print(f"\nHTML report:  {html_path}")

    if _write_golden_csv(results, csv_path):
        print(f"CSV written:  {csv_path}")
    else:
        print("CSV not written (no valid results).")

    if _write_champion_md(results, n_trades, champion_md_path):
        print(f"Champion MD:  {champion_md_path}")
    else:
        print("Champion MD not written (no valid results).")

    print("\n--- Graph ingest ---")
    print(f"  qw record --file {_CSV_PATH.relative_to(ROOT)} --kind baseline_csv")
    print(f"  qw record --file {_CHAMPION_MD_PATH.relative_to(ROOT)} --kind champion_md")
    print("\n--- Query ---")
    print("  qw query --name run_history --param strategy_id=btc-1d-bull-mars")
    print("  qw query --name rank_by_evidence --param strategy_id=btc-1d-bull-mars")


if __name__ == "__main__":
    main()
