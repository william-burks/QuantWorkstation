import numpy as np
import pandas as pd

from strategies.adapters.liquidity_sweep_adapter import prepare_data_from_frames, run_with_data


def _bars(index: pd.DatetimeIndex, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 75 + np.cumsum(rng.normal(0, 0.05, len(index)))
    high = close + rng.uniform(0.01, 0.08, len(index))
    low = close - rng.uniform(0.01, 0.08, len(index))
    open_ = close + rng.normal(0, 0.02, len(index))
    vol = rng.integers(100, 1000, len(index))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=index,
    )


def test_prepare_data_and_run_with_data_smoke() -> None:
    idx_5m = pd.date_range("2025-01-01", periods=300, freq="5min", tz="UTC")
    idx_1h = pd.date_range("2025-01-01", periods=80, freq="1h", tz="UTC")

    data = prepare_data_from_frames(
        cl5=_bars(idx_5m, seed=1),
        cl1h=_bars(idx_1h, seed=2),
        mes5=_bars(idx_5m, seed=3),
        mnq5=_bars(idx_5m, seed=4),
    )

    assert "atr" in data["cl5"].columns
    assert "atr" in data["cl1h"].columns
    assert str(data["cl5"].index.tz) == "US/Eastern"

    result = run_with_data(data)
    assert "metrics" in result
    assert "funnel" in result
    assert result["metrics"]["sample_size"] >= 0

