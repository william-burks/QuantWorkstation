# mypy: ignore-errors
"""Schema validation tests."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from data.schemas import Bar, FuturesContract, Position, Signal


def make_bar(**overrides):
    defaults = dict(
        symbol="BTC/USD",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=40000.0,
        high=41000.0,
        low=39000.0,
        close=40500.0,
        volume=100.0,
        market="crypto",
        source="alpaca",
    )
    return Bar(**{**defaults, **overrides})


def test_bar_valid():
    b = make_bar()
    assert b.symbol == "BTC/USD"
    assert b.adjusted is False


def test_bar_negative_price_rejected():
    with pytest.raises(ValidationError):
        make_bar(open=-1.0)


def test_bar_negative_volume_rejected():
    with pytest.raises(ValidationError):
        make_bar(volume=-10.0)


def test_futures_contract_valid():
    fc = FuturesContract(
        symbol="ES",
        expiry=date.fromisoformat("2024-03-15"),
        multiplier=50.0,
        margin=12000.0,
        front_month=True,
        continuous_symbol="ES_continuous",
    )
    assert fc.exchange == "CME"


def test_futures_contract_zero_multiplier_rejected():
    with pytest.raises(ValidationError):
        FuturesContract(
            symbol="ES",
            expiry=date.fromisoformat("2024-03-15"),
            multiplier=0.0,
            margin=12000.0,
            front_month=True,
            continuous_symbol="ES_continuous",
        )


def test_signal_valid():
    s = Signal(
        strategy="mars",
        symbol="ES_continuous",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        direction="long",
        strength=0.8,
    )
    assert s.params == {}


def test_signal_strength_out_of_range():
    with pytest.raises(ValidationError):
        Signal(
            strategy="mars",
            symbol="ES_continuous",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            direction="long",
            strength=1.5,
        )


def test_position_valid():
    p = Position(
        symbol="BTC/USD",
        market="crypto",
        qty=0.5,
        avg_price=40000.0,
        unrealized_pnl=250.0,
        broker="alpaca",
        risk=100.0,
        to_make=300.0,
    )
    assert p.qty == 0.5
