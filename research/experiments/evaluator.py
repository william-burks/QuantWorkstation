"""
Strategy evaluation: tier scoring, standardized reporting, and trade inspection.

Public API:
    tier()          — classify a single result against performance standards
    evaluate()      — add tier/beat_bh/fee_pct columns to sweep results DataFrame
    report()        — print standardized evaluation output for a trial
    worst_trades()  — return the N worst trades for a specific param combo
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from research.experiments.metrics import annual_pnl_breakdown
from research.experiments.standards import (
    CALMAR,
    MAX_DRAWDOWN_LIMIT,
    MIN_TRADES_PER_YEAR,
    PROFIT_FACTOR,
    SHARPE,
    TIERS,
)
from strategies.base import BaseStrategy

log = logging.getLogger(__name__)

# Columns produced by sweep() that are metrics (not strategy params)
_METRIC_COLS: frozenset[str] = frozenset(
    {
        "sharpe",
        "calmar",
        "max_drawdown",
        "return",
        "annual_return",
        "annual_volatility",
        "n_bars",
        "win_rate",
        "profit_factor",
        "n_trades",
        "gain",
        "fees",
        "beat_bh",
        "tier",
        "fee_pct_of_gain",
        "sample_size",
        "total_r",
        "avg_r_per_trade",
        "breakeven_win_rate",
        "strategy_return",
        "bh_exposure_return",
        "outperformance_x",
        "max_hours_in_market",
        "total_hours",
        "exposure_frac",
    }
)

_REGISTRY_PATH = Path(__file__).parent.parent / "results" / "registry.json"


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


def tier(
    sharpe_val: float,
    profit_factor_val: float,
    calmar_val: float,
    max_drawdown_val: float,
) -> str:
    """
    Classify a result against performance standards.

    Returns the lowest tier achieved across all four metrics.
    "fail" if max_drawdown is worse than the hard limit.
    """
    if max_drawdown_val < MAX_DRAWDOWN_LIMIT:
        return "fail"

    def _metric_tier(value: float, thresholds: dict[str, float]) -> str:
        if value >= thresholds["institutional"]:
            return "institutional"
        if value >= thresholds["professional"]:
            return "professional"
        if value >= thresholds["pass"]:
            return "pass"
        return "fail"

    tiers = [
        _metric_tier(sharpe_val, SHARPE),
        _metric_tier(profit_factor_val, PROFIT_FACTOR),
        _metric_tier(calmar_val, CALMAR),
    ]
    # Return the lowest tier (worst across all metrics)
    for t in reversed(TIERS):  # fail → pass → professional → institutional
        if t in tiers:
            return t
    return "fail"


# ---------------------------------------------------------------------------
# Evaluate: annotate sweep results DataFrame
# ---------------------------------------------------------------------------


def evaluate(results: pd.DataFrame, bh: dict[str, Any]) -> pd.DataFrame:
    """
    Add evaluation columns to sweep results.

    Adds:
        tier            — "institutional" | "professional" | "pass" | "fail"
        beat_bh         — True if strategy Sharpe > BH Sharpe
        fee_pct_of_gain — fees / gain (informational)

    Parameters
    ----------
    results : pd.DataFrame
        Output of sweep(). Must include sharpe, calmar, max_drawdown,
        profit_factor, fees, gain columns.
    bh : dict
        Buy-and-hold summary from metrics.summary().

    Returns
    -------
    pd.DataFrame
        results with tier, beat_bh, fee_pct_of_gain columns appended.
    """
    df = results.copy()

    # profit_factor may be missing if sweep was run without trade pnl (edge case)
    pf_col = (
        df["profit_factor"] if "profit_factor" in df.columns else pd.Series(0.0, index=df.index)
    )

    df["tier"] = [
        tier(row["sharpe"], pf_col.iloc[i], row["calmar"], row["max_drawdown"])
        for i, (_, row) in enumerate(df.iterrows())
    ]
    df["beat_bh"] = df["sharpe"] > bh["sharpe"]
    df["fee_pct_of_gain"] = (df["fees"] / df["gain"].replace(0, float("nan"))).round(4)

    return df


# ---------------------------------------------------------------------------
# Report: standardized trial output
# ---------------------------------------------------------------------------


def report(
    results: pd.DataFrame,
    bh: dict[str, Any],
    metadata: dict[str, Any],
    top_n: int = 3,
    full_n: int = 10,
    trades_df: pd.DataFrame | None = None,
) -> None:
    """
    Print standardized evaluation output for a trial.

    Expects results to already have tier/beat_bh columns (call evaluate() first).
    Auto-records any passing results to research/results/registry.json.

    Parameters
    ----------
    results : pd.DataFrame
        Evaluated sweep results (with tier column).
    bh : dict
        Buy-and-hold summary from metrics.summary().
    metadata : dict
        Trial metadata: symbol, freq, leverage, fees, sl_stop, tp_stop,
        time_stop, data_span, strategy (optional).
    top_n : int
        Number of rows to show in Top-N sections.
    full_n : int
        Number of rows to show in the full results table.
    trades_df : pd.DataFrame, optional
        Per-trade records with ``entry_time`` and ``pnl_usd`` columns.
        When provided, appends annual P&L breakdown after aggregate metrics.
    """
    _print_metadata(metadata)
    _print_bh(bh)

    if results.empty:
        print("\nNo valid results.")
        return

    _print_tier_assessment(results, bh)
    _print_top_n(results, bh, top_n, sort_by="sharpe", label="Sharpe")
    _print_top_n(results, bh, top_n, sort_by="return", label="Return")
    _print_full(results, full_n)
    if trades_df is not None and not trades_df.empty:
        print(_annual_breakdown(trades_df))
    _record_passing(results, metadata)


# ---------------------------------------------------------------------------
# Worst trades inspector
# ---------------------------------------------------------------------------


def worst_trades(
    strategy_cls: type[BaseStrategy],
    bars: pd.DataFrame,
    params: dict[str, Any],
    n: int = 3,
    *,
    freq: str = "1H",
    leverage: float = 1.0,
    fees: float = 0.000005,
    sl_stop: float = 0.008,
    tp_stop: float = 0.020,
    time_stop: int = 6,
    init_cash: float = 100_000.0,
) -> pd.DataFrame:
    """
    Return the N worst trades (by PnL) for a specific param combo.

    Re-runs the strategy once with the given params. Useful for diagnosing
    what market conditions are causing the largest losses.

    Parameters
    ----------
    strategy_cls : type[BaseStrategy]
        Strategy class to instantiate.
    bars : pd.DataFrame
        OHLCV bars.
    params : dict
        Strategy __init__ kwargs (param column values from sweep results).
    n : int
        Number of worst trades to return.

    Returns
    -------
    pd.DataFrame
        n rows sorted by pnl_usd ascending. Columns:
        entry_time, exit_time, direction, entry_price, exit_price,
        pnl_usd, pnl_pct, bars_held
    """
    # Local import keeps evaluate/report usable in environments without vectorbt.
    from strategies.adapters.vectorbt_adapter import run

    strategy = strategy_cls(**params)
    pf = run(
        strategy,
        bars,
        init_cash=init_cash,
        fees=fees,
        freq=freq,
        leverage=leverage,
        sl_stop=sl_stop,
        tp_stop=tp_stop,
        time_stop=time_stop,
    )

    trades = pf.trades
    count = int(trades.count())
    if count == 0:
        return pd.DataFrame()

    entry_idx = trades.entry_idx.values
    exit_idx = trades.exit_idx.values

    records = pd.DataFrame(
        {
            "entry_time": bars.index[entry_idx],
            "exit_time": bars.index[exit_idx],
            "direction": ["long" if d == 0 else "short" for d in trades.direction.values],
            "entry_price": trades.entry_price.values,
            "exit_price": trades.exit_price.values,
            "pnl_usd": trades.pnl.values,
            "pnl_pct": trades.return_.values,
            "bars_held": exit_idx - entry_idx,
        }
    )

    return records.sort_values("pnl_usd").head(n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Annual breakdown
# ---------------------------------------------------------------------------

_CONCENTRATION_THRESHOLD = 50.0  # pct


def _annual_breakdown(trades_df: pd.DataFrame) -> str:
    """
    Format annual P&L breakdown table and concentration warning.

    Returns a multi-line string ready to print.
    """
    rows = annual_pnl_breakdown(trades_df)
    if not rows:
        return ""

    sep = "=" * 10
    lines = [f"\n{sep} Annual Breakdown {sep}"]
    header = f"{'Year':<6} | {'Trades':>6} | {'Gross P&L':>10} | {'Sharpe':>6} | {'% of Total':>10}"
    divider = "-" * len(header)
    lines.append(header)
    lines.append(divider)
    for r in rows:
        lines.append(
            f"{r['year']:<6} | {r['trades']:>6} | "
            f"${r['gross_pnl']:>9,.0f} | {r['sharpe']:>6.2f} | {r['pct_of_total']:>9.1f}%"
        )

    # Concentration warning: strictly > 50%
    for r in rows:
        if r["pct_of_total"] > _CONCENTRATION_THRESHOLD:
            lines.append(
                f"\n[WARN] Regime concentration: "
                f"{r['year']} = {r['pct_of_total']:.1f}% of profit"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _print_metadata(metadata: dict[str, Any]) -> None:
    sep = "=" * 10
    print(f"\n{sep} METADATA {sep}")
    fields = [
        ("SYMBOL", metadata.get("symbol", "—")),
        ("FREQ", metadata.get("freq", "—")),
        ("LEVERAGE", metadata.get("leverage", "—")),
        ("FEES", metadata.get("fees", "—")),
        (
            "SL/TP",
            f"{metadata['sl_stop']:.1%} / {metadata['tp_stop']:.1%}"
            if "sl_stop" in metadata and "tp_stop" in metadata
            else "—",
        ),
        ("TIME_STOP", f"{metadata['time_stop']} bars" if "time_stop" in metadata else "—"),
        ("DATA_SPAN", metadata.get("data_span", "—")),
    ]
    for label, value in fields:
        print(f"{label}: {value}")


def _print_bh(bh: dict[str, Any]) -> None:
    sep = "=" * 10
    print(f"\n{sep} BUY & HOLD {sep}")
    print(
        f"  return={bh['return']:+.2%}   sharpe={bh['sharpe']:+.3f}   "
        f"dd={bh['max_drawdown']:+.2%}   calmar={bh['calmar']:+.3f}"
    )


def _print_tier_assessment(results: pd.DataFrame, bh: dict[str, Any]) -> None:
    sep = "=" * 10
    best = results.iloc[0]
    t = best.get("tier", "—")
    pf_val = best.get("profit_factor", float("nan"))

    def _flag(value: float, thresholds: dict[str, Any], hard_limit: float | None = None) -> str:
        if hard_limit is not None and value < hard_limit:
            return "FAIL"
        if value >= thresholds.get("institutional", float("inf")):
            return "INSTITUTIONAL"
        if value >= thresholds.get("professional", float("inf")):
            return "PROFESSIONAL"
        if value >= thresholds.get("pass", float("inf")):
            return "PASS"
        return "FAIL"

    sharpe_flag = _flag(best["sharpe"], SHARPE)
    pf_flag = _flag(pf_val, PROFIT_FACTOR)
    calmar_flag = _flag(best["calmar"], CALMAR)
    dd_flag = "PASS" if best["max_drawdown"] >= MAX_DRAWDOWN_LIMIT else "FAIL"

    failures = [
        m
        for m, f in [
            (f"Sharpe {best['sharpe']:.2f} < {SHARPE['pass']}", sharpe_flag == "FAIL"),
            (f"PF {pf_val:.2f} < {PROFIT_FACTOR['pass']}", pf_flag == "FAIL"),
            (f"Calmar {best['calmar']:.2f} < {CALMAR['pass']}", calmar_flag == "FAIL"),
            (f"DD {best['max_drawdown']:.1%} < {MAX_DRAWDOWN_LIMIT:.0%}", dd_flag == "FAIL"),
        ]
        if f
    ]

    tier_label = t.upper()
    reason = f"  ({' · '.join(failures)})" if failures else ""

    print(f"\n{sep} TIER ASSESSMENT (best result) {sep}")
    print(f"  {tier_label}{reason}")
    print(f"  Sharpe:        {best['sharpe']:.3f}   [{sharpe_flag:<13} — min {SHARPE['pass']}]")
    print(f"  Profit Factor: {pf_val:.3f}   [{pf_flag:<13} — min {PROFIT_FACTOR['pass']}]")
    print(f"  Calmar:        {best['calmar']:.3f}   [{calmar_flag:<13} — min {CALMAR['pass']}]")
    print(
        f"  Max Drawdown:  {best['max_drawdown']:+.2%}"
        f"  [{dd_flag:<13} — limit {MAX_DRAWDOWN_LIMIT:.0%}]"
    )
    beat = best.get("beat_bh", False)
    delta = best["sharpe"] - bh["sharpe"]
    bh_result = "YES" if beat else "NO"
    print(f"  Beat BH:       {bh_result}  ({delta:+.3f} vs BH sharpe {bh['sharpe']:.3f})")
    n_yr = results.get("n_trades", pd.Series()).iloc[0] if "n_trades" in results.columns else 0
    if n_yr < MIN_TRADES_PER_YEAR:
        print(f"  WARNING: {int(n_yr)} trades — below {MIN_TRADES_PER_YEAR}/yr reliability floor")


def _param_cols(results: pd.DataFrame) -> list[str]:
    return [c for c in results.columns if c not in _METRIC_COLS]


def _fmt_params(row: pd.Series, param_cols: list[str]) -> str:
    parts = []
    for c in param_cols:
        v = row[c]
        parts.append(f"{c}={int(v) if isinstance(v, float) and v == int(v) else v}")
    return "  ".join(parts)


def _print_top_n(
    results: pd.DataFrame,
    bh: dict[str, Any],
    n: int,
    sort_by: str,
    label: str,
) -> None:
    sep = "=" * 10
    top = results.sort_values(sort_by, ascending=False).head(n)
    pcols = _param_cols(results)
    print(f"\n{sep} TOP {n} by {label} {sep}")
    for _, row in top.iterrows():
        params_str = _fmt_params(row, pcols)
        sharpe_d = row["sharpe"] - bh["sharpe"]
        dd_d = row["max_drawdown"] - bh["max_drawdown"]
        ret_d = row["return"] - bh["return"]
        t = row.get("tier", "—").upper()
        print(
            f"  {params_str}  |  "
            f"sharpe={row['sharpe']:.3f} ({sharpe_d:+.3f})  "
            f"dd={row['max_drawdown']:+.2%} ({dd_d:+.2%})  "
            f"ret={row['return']:+.2%} ({ret_d:+.2%})  "
            f"[{t}]"
        )


def _print_full(results: pd.DataFrame, n: int) -> None:
    sep = "=" * 10
    pcols = _param_cols(results)
    display_cols = pcols + [
        "sharpe",
        "calmar",
        "max_drawdown",
        "return",
        "profit_factor",
        "win_rate",
        "n_trades",
        "gain",
        "fees",
        "fee_pct_of_gain",
        "tier",
    ]
    available = [c for c in display_cols if c in results.columns]
    print(f"\n{sep} TOP {n} RESULTS {sep}")
    print(results[available].head(n).to_string(index=True))


def _record_passing(results: pd.DataFrame, metadata: dict[str, Any]) -> None:
    """Append any passing results to the registry file."""

    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return value
        return value

    passing = results[results.get("tier", pd.Series("fail", index=results.index)) != "fail"]
    if passing.empty:
        return

    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if _REGISTRY_PATH.exists():
        try:
            existing = json.loads(_REGISTRY_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []

    pcols = _param_cols(results)
    metric_keys = [
        "sharpe",
        "calmar",
        "max_drawdown",
        "return",
        "profit_factor",
        "win_rate",
        "n_trades",
    ]

    # Record the best result per tier
    recorded_tiers = []
    for t in ["institutional", "professional", "pass"]:
        subset = passing[passing["tier"] == t]
        if subset.empty:
            continue
        row = subset.sort_values("sharpe", ascending=False).iloc[0]
        entry = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "strategy": metadata.get("strategy", "unknown"),
            "symbol": metadata.get("symbol", "unknown"),
            "freq": metadata.get("freq", "unknown"),
            "tier": t,
            "params": _json_safe({c: row[c] for c in pcols}),
            "metrics": {k: round(float(row[k]), 6) for k in metric_keys if k in row},
            "beat_bh": bool(row.get("beat_bh", False)),
            "metadata": _json_safe(
                {
                    k: v
                    for k, v in metadata.items()
                    if k not in ("data_span", "strategy", "symbol", "freq")
                }
            ),
        }
        existing.append(entry)
        recorded_tiers.append(t.upper())

    _REGISTRY_PATH.write_text(json.dumps(existing, indent=2))
    print(f"\n  → Recorded to registry: {', '.join(recorded_tiers)}  ({_REGISTRY_PATH})")
