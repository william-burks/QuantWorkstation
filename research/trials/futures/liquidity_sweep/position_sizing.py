"""Position sizing utilities for liquidity sweep trade replay."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from research.experiments.metrics import summary


def _as_trade_index(trades: pd.DataFrame) -> pd.Index:
    if "entry_time" in trades.columns:
        return pd.to_datetime(trades["entry_time"])
    return trades.index


def build_sized_equity(
    trades: pd.DataFrame,
    mode: str,
    *,
    base_risk: float = 0.01,
    min_risk: float = 0.0025,
    max_risk: float = 0.02,
    dd_threshold: float = 0.02,
    dd_scale: float = 0.5,
    streak_len: int = 2,
    streak_scale: float = 0.5,
    start_equity: float = 100_000.0,
) -> pd.DataFrame:
    """Replay R-multiple trades under a position sizing policy."""
    if trades.empty:
        return pd.DataFrame(columns=["risk_pct", "trade_return", "equity"])

    pnl_r = trades["pnl_r"].astype(float).to_numpy()
    r_dist = trades.get("r_dist", pd.Series(np.nan, index=trades.index)).astype(float).to_numpy()
    idx = _as_trade_index(trades)

    median_rdist = np.nanmedian(r_dist) if np.isfinite(r_dist).any() else np.nan
    risks = np.zeros(len(trades), dtype=float)
    trade_returns = np.zeros(len(trades), dtype=float)
    equity = np.zeros(len(trades), dtype=float)

    eq = float(start_equity)
    peak = eq
    loss_streak = 0

    for i in range(len(trades)):
        risk = base_risk

        if mode == "drawdown_scale":
            dd = (eq / peak) - 1.0
            if dd <= -abs(dd_threshold):
                risk *= dd_scale
        elif mode == "loss_streak":
            if loss_streak >= streak_len:
                risk *= streak_scale
        elif mode == "rdist_vol_target":
            if np.isfinite(median_rdist) and np.isfinite(r_dist[i]) and r_dist[i] > 0:
                scale = float(np.clip(median_rdist / r_dist[i], 0.5, 1.5))
                risk *= scale

        risk = float(np.clip(risk, min_risk, max_risk))
        tr = pnl_r[i] * risk
        eq *= 1.0 + tr
        peak = max(peak, eq)

        if pnl_r[i] < 0:
            loss_streak += 1
        elif pnl_r[i] > 0:
            loss_streak = 0

        risks[i] = risk
        trade_returns[i] = tr
        equity[i] = eq

    return pd.DataFrame(
        {"risk_pct": risks, "trade_return": trade_returns, "equity": equity},
        index=idx,
    )


def exposure_normalized(
    strategy_return: float,
    bh_return: float,
    n_trades: int,
    max_hold_bars_5m: int,
    total_hours: int,
) -> dict[str, float]:
    max_hours_in_market = n_trades * max_hold_bars_5m * (5 / 60)
    exposure_frac = (max_hours_in_market / total_hours) if total_hours > 0 else np.nan
    bh_exposure_return = bh_return * exposure_frac
    outperformance_x = strategy_return / bh_exposure_return if bh_exposure_return not in (0, np.nan) else np.nan
    return {
        "max_hours_in_market": float(max_hours_in_market),
        "total_hours": float(total_hours),
        "exposure_frac": float(exposure_frac),
        "bh_exposure_return": float(bh_exposure_return),
        "outperformance_x": float(outperformance_x),
    }


def evaluate_sizing_modes(
    trades: pd.DataFrame,
    mode_rows: Iterable[dict],
    *,
    bh_return: float,
    max_hold_bars_5m: int,
    total_hours: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return summary table and stacked equity curves for sizing mode experiments."""
    summaries: list[dict] = []
    curves: list[pd.DataFrame] = []

    for row in mode_rows:
        label = row["label"]
        mode = row["mode"]
        kwargs = {k: v for k, v in row.items() if k not in {"label", "mode"}}
        replay = build_sized_equity(trades, mode, **kwargs)
        if replay.empty:
            continue

        metrics = summary(replay["equity"], replay["trade_return"])
        exp = exposure_normalized(
            strategy_return=float(metrics["return"]),
            bh_return=float(bh_return),
            n_trades=len(replay),
            max_hold_bars_5m=max_hold_bars_5m,
            total_hours=total_hours,
        )
        summaries.append(
            {
                "label": label,
                "mode": mode,
                "n_trades": len(replay),
                "risk_avg": float(replay["risk_pct"].mean()),
                "return": float(metrics["return"]),
                "sharpe": float(metrics["sharpe"]),
                "calmar": float(metrics["calmar"]),
                "max_drawdown": float(metrics["max_drawdown"]),
                "win_rate": float(metrics["win_rate"]),
                "profit_factor": float(metrics["profit_factor"]),
                **exp,
            }
        )

        curve = replay[["equity"]].copy()
        curve["label"] = label
        curves.append(curve.reset_index(names="time"))

    summary_df = pd.DataFrame(summaries).sort_values(
        ["sharpe", "return", "calmar"], ascending=[False, False, False]
    ).reset_index(drop=True)
    curves_df = pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()
    return summary_df, curves_df

