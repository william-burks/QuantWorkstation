"""Quote schema tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from data.schemas import Quote


def make_quote(**overrides):
    defaults = dict(
        symbol="BTC/USD",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        bid=40000.0,
        ask=40010.0,
        bid_size=0.5,
        ask_size=0.3,
        market="crypto",
        source="alpaca",
    )
    return Quote(**{**defaults, **overrides})


def test_quote_valid():
    q = make_quote()
    assert q.symbol == "BTC/USD"


def test_quote_mid():
    q = make_quote(bid=40000.0, ask=40010.0)
    assert q.mid == 40005.0


def test_quote_spread():
    q = make_quote(bid=40000.0, ask=40010.0)
    assert q.spread == 10.0


def test_quote_negative_bid_rejected():
    with pytest.raises(ValidationError):
        make_quote(bid=-1.0)


def test_quote_negative_ask_rejected():
    with pytest.raises(ValidationError):
        make_quote(ask=-1.0)


def test_quote_futures_market():
    q = make_quote(symbol="ES_continuous", market="futures", source="ibkr")
    assert q.market == "futures"
