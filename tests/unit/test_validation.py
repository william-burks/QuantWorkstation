"""Unit tests for data.validation.validate_bars."""

from __future__ import annotations

import warnings
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from data.validation import validate_bars

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_df(
    n: int = 5,
    freq: str = "h",
    start: str = "2024-01-01 00:00:00",
    tz: str = "UTC",
    price: float = 100.0,
) -> pd.DataFrame:
    """Return a clean OHLCV DataFrame."""
    index = pd.date_range(start, periods=n, freq=freq, tz=tz)
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000.0,
        },
        index=index,
    )


# ── Clean pass ────────────────────────────────────────────────────────────────


def test_clean_pass_no_error_no_warning() -> None:
    recent = datetime.now(tz=UTC) - timedelta(hours=24)
    df = _make_df(n=24, freq="h", start=recent.strftime("%Y-%m-%d %H:%M:%S"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_bars(df, freq="h")  # must not raise


def test_empty_df_no_error() -> None:
    df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df.index = pd.DatetimeIndex([], tz="UTC")
    validate_bars(df, freq="1H")


# ── P1: UTC timezone ─────────────────────────────────────────────────────────


def test_p1_no_timezone_raises() -> None:
    df = _make_df(tz=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timezone must be UTC"):
        validate_bars(df, freq="1H")


def test_p1_non_utc_timezone_raises() -> None:
    df = _make_df(tz="US/Eastern")
    with pytest.raises(ValueError, match="timezone must be UTC"):
        validate_bars(df, freq="1H")


# ── P1: Unique timestamps ─────────────────────────────────────────────────────


def test_p1_duplicate_timestamps_raises() -> None:
    df = _make_df(n=3)
    df = pd.concat([df, df.iloc[:1]])
    df = df.sort_index()
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        validate_bars(df, freq="1H")


# ── P1: NaN prices ────────────────────────────────────────────────────────────


def test_p1_nan_open_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "open"] = float("nan")
    with pytest.raises(ValueError, match="NaN prices"):
        validate_bars(df, freq="1H")


def test_p1_nan_close_raises() -> None:
    df = _make_df()
    df.loc[df.index[1], "close"] = float("nan")
    with pytest.raises(ValueError, match="NaN prices"):
        validate_bars(df, freq="1H")


# ── P1: Zero prices ───────────────────────────────────────────────────────────


def test_p1_zero_low_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "low"] = 0.0
    df.loc[df.index[0], "open"] = 0.0
    df.loc[df.index[0], "close"] = 0.0
    with pytest.raises(ValueError, match="Zero prices"):
        validate_bars(df, freq="1H")


def test_p1_zero_high_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "high"] = 0.0
    df.loc[df.index[0], "low"] = 0.0
    df.loc[df.index[0], "open"] = 0.0
    df.loc[df.index[0], "close"] = 0.0
    with pytest.raises(ValueError, match="Zero prices"):
        validate_bars(df, freq="1H")


# ── P1: Negative prices ────────────────────────────────────────────────────────


def test_p1_negative_close_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "close"] = -1.0
    df.loc[df.index[0], "low"] = -2.0
    with pytest.raises(ValueError, match="Negative prices"):
        validate_bars(df, freq="1H")


# ── P1: high >= low ────────────────────────────────────────────────────────────


def test_p1_high_less_than_low_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "high"] = 99.0
    df.loc[df.index[0], "low"] = 101.0
    with pytest.raises(ValueError, match="high < low"):
        validate_bars(df, freq="1H")


# ── P1: close in [low, high] ──────────────────────────────────────────────────


def test_p1_close_above_high_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "close"] = 110.0  # high=101
    with pytest.raises(ValueError, match="close out of"):
        validate_bars(df, freq="1H")


def test_p1_close_below_low_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "close"] = 90.0  # low=99
    with pytest.raises(ValueError, match="close out of"):
        validate_bars(df, freq="1H")


# ── P1: open in [low, high] ───────────────────────────────────────────────────


def test_p1_open_above_high_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "open"] = 110.0  # high=101
    with pytest.raises(ValueError, match="open out of"):
        validate_bars(df, freq="1H")


def test_p1_open_below_low_raises() -> None:
    df = _make_df()
    df.loc[df.index[0], "open"] = 90.0  # low=99
    with pytest.raises(ValueError, match="open out of"):
        validate_bars(df, freq="1H")


# ── P2: Gap detection ─────────────────────────────────────────────────────────


def test_p2_large_gap_warns() -> None:
    df = _make_df(n=5, freq="1H")
    # Insert a 3-hour gap between bar 2 and bar 3 (> 2× expected 1H spacing)
    idx = df.index.tolist()
    idx[2] = idx[1] + timedelta(hours=4)
    idx[3] = idx[2] + timedelta(hours=1)
    idx[4] = idx[3] + timedelta(hours=1)
    df.index = pd.DatetimeIndex(idx, tz="UTC")
    with pytest.warns(UserWarning, match="Gap detected"):
        validate_bars(df, freq="1H")


def test_p2_no_gap_no_warning() -> None:
    recent = datetime.now(tz=UTC) - timedelta(hours=5)
    df = _make_df(n=5, freq="h", start=recent.strftime("%Y-%m-%d %H:%M:%S"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_bars(df, freq="h")


# ── P2: Stale feed ────────────────────────────────────────────────────────────


def test_p2_stale_feed_warns() -> None:
    # Last bar is 10 hours ago — well past 3× 1H spacing
    stale_start = datetime.now(tz=UTC) - timedelta(hours=14)
    df = _make_df(n=5, freq="1H", start=stale_start.strftime("%Y-%m-%d %H:%M:%S"))
    with pytest.warns(UserWarning, match="Stale feed"):
        validate_bars(df, freq="1H")


def test_p2_fresh_feed_no_warning() -> None:
    # Last bar is recent (within 1× 1H spacing)
    fresh_start = datetime.now(tz=UTC) - timedelta(minutes=30)
    df = _make_df(n=1, freq="1H", start=fresh_start.strftime("%Y-%m-%d %H:%M:%S"))
    # Suppress gap warning (only 1 bar so no diffs), check no stale warning
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate_bars(df, freq="1H")
    stale = [w for w in caught if "Stale feed" in str(w.message)]
    assert not stale


# ── P2: Schema drift ──────────────────────────────────────────────────────────


def test_p2_missing_ohlc_columns_warns() -> None:
    df = pd.DataFrame(
        {"volume": [100, 200]},
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )
    with pytest.warns(UserWarning, match="Schema drift"):
        validate_bars(df, freq="1H")


def test_p2_missing_single_column_warns() -> None:
    df = _make_df(n=3)
    df = df.drop(columns=["close"])
    with pytest.warns(UserWarning, match="Schema drift"):
        validate_bars(df, freq="1H")


# ── P3: Row count undercount ──────────────────────────────────────────────────


def test_p3_low_row_count_warns() -> None:
    # Build a df spanning 48 hours but with only 10 bars (< 95% of 49 expected)
    index = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    # Force last bar to 48 hours after first — creates sparse coverage
    lst = list(index)
    lst[-1] = lst[0] + timedelta(hours=48)
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000.0,
        },
        index=pd.DatetimeIndex(lst, tz="UTC"),
    )
    with pytest.warns(UserWarning, match="95%"):
        validate_bars(df, freq="1H")


def test_p3_full_count_no_warning() -> None:
    recent = datetime.now(tz=UTC) - timedelta(hours=48)
    df = _make_df(n=48, freq="h", start=recent.strftime("%Y-%m-%d %H:%M:%S"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_bars(df, freq="h")
