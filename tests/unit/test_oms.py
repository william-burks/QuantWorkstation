import pytest

from execution.oms import OMS
from execution.risk import RiskEngine
from execution.types import PositionState

BALANCE = 100_000.0


@pytest.fixture
def risk() -> RiskEngine:
    engine = RiskEngine(eval_profit_target=3000.0)
    engine.seed(BALANCE)
    return engine


@pytest.fixture
def oms(risk: RiskEngine) -> OMS:
    return OMS(risk)


def _pos(symbol: str, qty: float, price: float) -> PositionState:
    market_value = qty * price
    return PositionState(
        symbol=symbol,
        qty=qty,
        avg_entry_price=price,
        market_value=market_value,
        unrealized_pnl=0.0,
    )


# --- Basic rebalance ---


def test_open_new_position(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={"BTC/USD": 5000.0},
        current=[],
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].symbol == "BTC/USD"
    assert orders[0].notional == pytest.approx(5000.0)


def test_close_position_not_in_targets(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={},
        current=[_pos("BTC/USD", 0.1, 50_000.0)],
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].qty == pytest.approx(0.1)


def test_close_position_with_zero_target(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={"BTC/USD": 0.0},
        current=[_pos("BTC/USD", 0.1, 50_000.0)],
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].side == "sell"


def test_increase_position(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={"BTC/USD": 6000.0},
        current=[_pos("BTC/USD", 0.1, 50_000.0)],  # market_value=5000
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].notional == pytest.approx(1000.0)


def test_decrease_position(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={"BTC/USD": 4000.0},
        current=[_pos("BTC/USD", 0.1, 50_000.0)],  # market_value=5000
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].notional == pytest.approx(1000.0)


def test_no_order_for_sub_dollar_delta(oms: OMS) -> None:
    orders = oms.rebalance(
        targets={"BTC/USD": 5000.50},
        current=[_pos("BTC/USD", 0.1, 50_000.0)],  # market_value=5000
        account_equity=BALANCE,
    )
    assert len(orders) == 0


# --- Risk integration ---


def test_risk_blocked_order_skipped(oms: OMS, risk: RiskEngine) -> None:
    # Force a halt
    risk.update(BALANCE * 0.94)  # trip 5% daily loss
    orders = oms.rebalance(
        targets={"BTC/USD": 5000.0},
        current=[],
        account_equity=BALANCE,
    )
    # Blocked by risk — no orders generated
    assert len(orders) == 0


def test_symbol_exposure_capped_by_risk(oms: OMS) -> None:
    # Request 10% of equity — risk caps at 5%
    orders = oms.rebalance(
        targets={"BTC/USD": BALANCE * 0.10},
        current=[],
        account_equity=BALANCE,
    )
    assert len(orders) == 1
    assert orders[0].notional == pytest.approx(BALANCE * 0.05)
