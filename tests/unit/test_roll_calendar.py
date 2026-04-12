"""Roll calendar + continuous series builder tests."""

from datetime import date

import pandas as pd
import pytest

from data.collectors.roll_calendar import build_continuous, get_roll_date


def _make_bars(dates: list[str], base_price: float) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") for d in dates])
    return pd.DataFrame(
        {
            "open": base_price,
            "high": base_price * 1.01,
            "low": base_price * 0.99,
            "close": base_price,
            "volume": 1000.0,
            "market": "futures",
            "source": "ibkr",
            "adjusted": False,
        },
        index=idx,
    )


def test_get_roll_date_is_before_expiry():
    expiry = date(2024, 3, 15)
    roll = get_roll_date(expiry)
    assert roll < expiry


def test_build_continuous_single_contract():
    expiry = date(2024, 3, 15)
    contracts = pd.DataFrame([{"expiry": expiry, "front_month": True}])
    bars = _make_bars(["2024-01-02", "2024-01-03", "2024-01-04"], 4800.0)
    result = build_continuous("ES", contracts, {expiry: bars})
    assert len(result) == 3
    assert result["adjusted"].all()


def test_build_continuous_two_contracts_ratio_applied():
    expiry1 = date(2024, 3, 15)
    expiry2 = date(2024, 6, 21)
    contracts = pd.DataFrame([
        {"expiry": expiry1, "front_month": False},
        {"expiry": expiry2, "front_month": True},
    ])
    # Old contract closes at 4800, new at 4820 on roll date
    # Ratio = 4820/4800 ≈ 1.00417, so old bars get multiplied
    bars1 = _make_bars(["2024-01-02", "2024-01-03"], 4800.0)
    bars2 = _make_bars(["2024-03-08", "2024-03-09", "2024-04-01"], 4820.0)

    result = build_continuous("ES", contracts, {expiry1: bars1, expiry2: bars2})
    assert not result.empty
    assert result["adjusted"].all()
    # All prices from old contract should be scaled up by the roll ratio
    old_segment = result[result.index < pd.Timestamp("2024-03-08", tz="UTC")]
    if not old_segment.empty:
        assert old_segment["close"].iloc[0] > 4800.0


def test_build_continuous_empty_contracts_raises():
    with pytest.raises(ValueError):
        build_continuous("ES", pd.DataFrame(), {})


def test_build_continuous_no_valid_segments_raises():
    expiry = date(2024, 3, 15)
    contracts = pd.DataFrame([{"expiry": expiry, "front_month": True}])
    with pytest.raises(ValueError):
        build_continuous("ES", contracts, {})  # no bars provided
