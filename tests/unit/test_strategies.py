import numpy as np
import pandas as pd
import pytest

from strategies.mars import MARS


def _make_bars(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 40_000 + np.cumsum(rng.normal(0, 500, n))
    close = np.clip(close, 1, None)
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": rng.uniform(1, 10, n)},
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )


BARS = _make_bars()

# --- MARS ---

class TestMARS:
    def test_signal_shape(self) -> None:
        sig = MARS().generate_signals(BARS)
        assert len(sig) == len(BARS)
        assert sig.index.equals(BARS.index)

    def test_signal_values(self) -> None:
        sig = MARS().generate_signals(BARS)
        assert set(sig.unique()).issubset({-1, 0, 1})

    def test_signal_name(self) -> None:
        assert MARS().generate_signals(BARS).name == "mars"

    def test_invalid_trend_less_than_mom(self) -> None:
        with pytest.raises(ValueError):
            MARS(mom_period=50, trend_period=20)

    def test_invalid_vol_threshold(self) -> None:
        with pytest.raises(ValueError):
            MARS(vol_threshold=1.5)
