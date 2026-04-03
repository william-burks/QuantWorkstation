import pandas as pd

from research.trials.futures.liquidity_sweep.position_sizing import (
    build_sized_equity,
    evaluate_sizing_modes,
)


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "entry_time": pd.date_range("2025-01-01", periods=5, freq="1D", tz="UTC"),
            "pnl_r": [1.0, -1.0, -1.0, 1.25, 1.0],
            "r_dist": [0.2, 0.1, 0.4, 0.2, 0.1],
        }
    )


def test_fixed_mode_uses_constant_risk() -> None:
    replay = build_sized_equity(_trades(), mode="fixed", base_risk=0.01)
    assert (replay["risk_pct"] == 0.01).all()
    assert len(replay) == 5


def test_loss_streak_scales_risk_after_two_losses() -> None:
    replay = build_sized_equity(
        _trades(),
        mode="loss_streak",
        base_risk=0.01,
        streak_len=2,
        streak_scale=0.5,
    )
    # Third loss means next trade is risk-throttled.
    assert replay["risk_pct"].iloc[3] == 0.005


def test_evaluate_modes_returns_sorted_summary() -> None:
    summary_df, curves_df = evaluate_sizing_modes(
        _trades(),
        mode_rows=[
            {"label": "low", "mode": "fixed", "base_risk": 0.0025},
            {"label": "high", "mode": "fixed", "base_risk": 0.01},
        ],
        bh_return=0.10,
        max_hold_bars_5m=24,
        total_hours=1000,
    )
    assert not summary_df.empty
    assert {"label", "return", "outperformance_x"}.issubset(summary_df.columns)
    assert not curves_df.empty

