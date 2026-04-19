# mypy: ignore-errors
"""Shared trial scaffolding — extracted from existing trial scripts.

All trials should import from here instead of re-implementing boilerplate.
Exports: prepare_data, compute_metrics, write_html, make_bundle, best_metrics, write_bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Exponentially weighted Average True Range."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def prepare_data(df: pd.DataFrame, atr_period: int = 14) -> pd.DataFrame:
    """Standard data preparation: parse timestamps, cast numerics, compute ATR.

    Returns copy of df with:
      - UTC DatetimeIndex
      - numeric open/high/low/close/volume columns
      - atr column
      - rows with NaN ATR dropped
    """
    out = df.copy()
    out.index = pd.to_datetime(out.index, utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.sort_index()
    out["atr"] = _compute_atr(out, atr_period)
    return out.dropna(subset=["atr"])


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(trades: pd.DataFrame, window: str, equity: pd.Series) -> dict | None:
    """Compute standard metrics dict from trades DataFrame and equity curve.

    Args:
        trades: DataFrame with columns including pnl_r, outcome, entry_time, bars_held
        window: label string (e.g. "IS", "OOS")
        equity: equity curve pd.Series (1-indexed float values)

    Returns dict with standard keys or None if trades is empty.
    """
    if trades.empty:
        return None

    from research.experiments.metrics import summary as _summary

    trade_ret = equity.pct_change().dropna()
    m = _summary(equity, trade_ret)

    pnl = trades["pnl_r"]
    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    loser_sum = abs(losers.sum())
    pf = float(winners.sum() / loser_sum) if loser_sum > 1e-9 else 99.99

    wins = (trades["outcome"] == "WIN").sum() if "outcome" in trades.columns else 0
    return {
        "window": window,
        "total_trades": len(trades),
        "win_rate": wins / len(trades),
        "profit_factor": pf,
        "sharpe": m["sharpe"],
        "max_drawdown": m["max_drawdown"],
        "calmar": m["calmar"],
        "total_r": float(pnl.sum()),
        "avg_bars_held": float(trades["bars_held"].mean())
        if "bars_held" in trades.columns
        else 0.0,
        "first_trade_ts": pd.Timestamp(trades["entry_time"].min()).isoformat()
        if "entry_time" in trades.columns
        else "",
        "last_trade_ts": pd.Timestamp(trades["entry_time"].max()).isoformat()
        if "entry_time" in trades.columns
        else "",
    }


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------


def write_html(
    rows: list[dict],
    trades_by_window: dict,
    output_path: Path,
    title: str = "Trial Results",
    hypothesis_id: str = "",
    config: dict | None = None,
) -> None:
    """Write IS/OOS summary + per-trade table HTML report.

    Args:
        rows: list of metrics dicts (one per window)
        trades_by_window: dict mapping window label → trades DataFrame
        output_path: destination .html path
        title: page title
        hypothesis_id: hypothesis ID string for display
        config: config dict for display in page header
    """
    df = pd.DataFrame(rows)
    fmt = {
        "win_rate": "{:.1%}",
        "profit_factor": "{:.3f}",
        "sharpe": "{:.3f}",
        "max_drawdown": "{:+.2%}",
        "calmar": "{:.2f}",
        "total_r": "{:.4f}",
        "avg_bars_held": "{:.1f}",
    }
    styled = df.copy()
    for col, f in fmt.items():
        if col in styled.columns:
            styled[col] = styled[col].apply(lambda v: f.format(v) if isinstance(v, float) else v)
    summary_table = styled.to_html(index=False, border=0, classes="table")

    trade_tables = ""
    for window, tdf in trades_by_window.items():
        cols = ["entry_time", "exit_time", "bars_held", "pnl_r", "outcome"]
        available = [c for c in cols if c in tdf.columns]
        tdf_fmt = tdf[available].copy()
        if "pnl_r" in tdf_fmt.columns:
            tdf_fmt["pnl_r"] = tdf_fmt["pnl_r"].apply(lambda v: f"{v:+.3f}R")
        trade_tables += f"<h2>{window} Trades</h2>"
        trade_tables += tdf_fmt.to_html(index=False, border=0, classes="table")

    config_str = ""
    if config:
        config_str = "  ".join(f"{k}={v}" for k, v in config.items())

    hyp_line = f"<p>Hypothesis <code>{hypothesis_id}</code></p>" if hypothesis_id else ""
    cfg_line = f'<p class="cfg">{config_str}</p>' if config_str else ""

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin-bottom: 28px; }}
    .table {{ border-collapse: collapse; width: 100%; margin-bottom: 8px; }}
    .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
    .table th {{ background: #f7f7f7; }}
    .cfg {{ font-size: 12px; color: #888; margin-bottom: 20px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  {hyp_line}
  {cfg_line}
  <section>
    <h2>Summary</h2>
    {summary_table}
  </section>
  <section>
    {trade_tables}
  </section>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


# ---------------------------------------------------------------------------
# Bundle manifest
# ---------------------------------------------------------------------------


def best_metrics(rows: list[dict], min_trades: int = 10) -> dict | None:
    """Return metrics summary dict for the best row in a results list.

    Picks the row with highest sharpe among rows where total_trades >= min_trades.
    Falls back to highest sharpe overall if no row meets the trades threshold.
    Returns a standardised subset: sharpe, max_drawdown, win_rate, total_trades, calmar.
    Returns None if rows is empty.
    """
    if not rows:
        return None
    qualified = [r for r in rows if r.get("total_trades", 0) >= min_trades]
    pool = qualified if qualified else rows
    best = max(pool, key=lambda r: r.get("sharpe", float("-inf")))
    return {
        "sharpe": best.get("sharpe"),
        "max_drawdown": best.get("max_drawdown"),
        "win_rate": best.get("win_rate"),
        "total_trades": best.get("total_trades"),
        "calmar": best.get("calmar"),
    }


def make_bundle(
    trial_name: str,
    hypothesis_id: str,
    run_ts: str,
    files: dict,
    metrics: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """Build bundle.json manifest dict.

    Args:
        trial_name: trial identifier string (e.g. "btc_donchian_01_baseline")
        hypothesis_id: 12-char hypothesis ID — REQUIRED for qw record --bundle
        run_ts: timestamp string (YYYYmmdd-HHMMSS)
        files: dict mapping role → filename, e.g. {"csv": "results.csv", "html": "results.html"}
        metrics: optional best-row metrics summary (use best_metrics(rows) helper).
                 Stored as metrics_summary for navigator pivot analysis.
        extra: optional additional top-level fields

    Returns dict ready for json.dumps.
    """
    bundle: dict = {
        "trial": trial_name,
        "hypothesis_id": hypothesis_id,
        "run_ts": run_ts,
        "files": files,
    }
    if metrics:
        bundle["metrics_summary"] = metrics
    if extra:
        bundle.update(extra)
    return bundle


def write_bundle(bundle: dict, run_dir: Path) -> Path:
    """Write bundle dict to run_dir/bundle.json. Returns path."""
    path = run_dir / "bundle.json"
    path.write_text(json.dumps(bundle, indent=2))
    return path
