import pytest

from execution.risk import (
    COMPLIANCE_LOT_FRACTION,
    CONSISTENCY_THRESHOLD,
    DAILY_PROFIT_CEILING_PCT,
    MAX_DAILY_LOSS_PCT,
    MAX_TOTAL_DRAWDOWN_PCT,
    RiskEngine,
    RiskViolation,
    TradingState,
)

GOAL = 3000.0
BALANCE = 100_000.0


@pytest.fixture
def risk() -> RiskEngine:
    engine = RiskEngine(eval_profit_target=GOAL)
    engine.seed(BALANCE)
    return engine


# --- Daily loss halt ---

def test_daily_loss_halt(risk: RiskEngine) -> None:
    loss_equity = BALANCE * (1 - MAX_DAILY_LOSS_PCT) - 0.01
    state = risk.update(loss_equity)
    assert state == TradingState.DAILY_LOSS_HALT
    assert risk.is_halted()


def test_daily_loss_below_threshold_stays_trading(risk: RiskEngine) -> None:
    safe_equity = BALANCE * (1 - MAX_DAILY_LOSS_PCT) + 1.0
    state = risk.update(safe_equity)
    assert state == TradingState.TRADING


# --- Trailing drawdown halt ---

def test_drawdown_halt(risk: RiskEngine) -> None:
    # Push HWM up first
    risk.update(BALANCE * 1.05)
    # Then drop below 10% of new HWM
    hwm = BALANCE * 1.05
    breach_equity = hwm * (1 - MAX_TOTAL_DRAWDOWN_PCT) - 0.01
    state = risk.update(breach_equity)
    assert state == TradingState.DRAWDOWN_HALT
    assert risk.is_halted()


# --- Daily profit ceiling ---

def test_daily_cap_hit(risk: RiskEngine) -> None:
    cap_equity = BALANCE * (1 + DAILY_PROFIT_CEILING_PCT) + 0.01
    state = risk.update(cap_equity)
    assert state == TradingState.DAILY_CAP_HIT


def test_daily_cap_blocks_orders(risk: RiskEngine) -> None:
    risk.update(BALANCE * (1 + DAILY_PROFIT_CEILING_PCT) + 1.0)
    with pytest.raises(RiskViolation, match="profit cap"):
        risk.check_order("BTC/USD", 1000.0, BALANCE, 0.0)


# --- Day reset ---

def test_day_reset_lifts_daily_loss_halt(risk: RiskEngine) -> None:
    risk.update(BALANCE * (1 - MAX_DAILY_LOSS_PCT) - 1.0)
    assert risk.is_halted()
    risk.reset_day(BALANCE)
    assert risk.state == TradingState.TRADING


def test_day_reset_does_not_lift_drawdown_halt(risk: RiskEngine) -> None:
    # Drawdown halt is permanent until manual intervention (max drawdown from peak)
    risk.update(BALANCE * 1.05)  # push HWM
    risk.update(BALANCE * 1.05 * (1 - MAX_TOTAL_DRAWDOWN_PCT) - 1.0)
    assert risk.state == TradingState.DRAWDOWN_HALT
    risk.reset_day(BALANCE)
    # Drawdown halt persists — it's a hard kill-switch
    assert risk.state == TradingState.DRAWDOWN_HALT


# --- Consistency / compliance mode ---

def test_compliance_mode_triggered(risk: RiskEngine) -> None:
    # Simulate a best day that exceeds 30% of eval goal
    profit = GOAL * CONSISTENCY_THRESHOLD + 1.0
    risk.update(BALANCE + profit)
    assert risk.state == TradingState.COMPLIANCE_MODE


def test_compliance_mode_caps_notional(risk: RiskEngine) -> None:
    profit = GOAL * CONSISTENCY_THRESHOLD + 1.0
    risk.update(BALANCE + profit)
    approved = risk.check_order("BTC/USD", 5000.0, BALANCE, 0.0)
    assert approved == pytest.approx(BALANCE * COMPLIANCE_LOT_FRACTION)


# --- Order checks ---

def test_symbol_exposure_capped(risk: RiskEngine) -> None:
    # Request more than 5% of equity
    approved = risk.check_order("BTC/USD", BALANCE * 0.10, BALANCE, 0.0)
    assert approved == pytest.approx(BALANCE * 0.05)


def test_total_exposure_blocks_order(risk: RiskEngine) -> None:
    # Existing exposure already at 40%
    with pytest.raises(RiskViolation, match="40%"):
        risk.check_order("ETH/USD", 1000.0, BALANCE, BALANCE * 0.40)


def test_total_exposure_reduces_order(risk: RiskEngine) -> None:
    # $500 remaining before 40% cap
    existing = BALANCE * 0.40 - 500.0
    approved = risk.check_order("BTC/USD", 1000.0, BALANCE, existing)
    assert approved == pytest.approx(500.0)


def test_halted_blocks_all_orders(risk: RiskEngine) -> None:
    risk.update(BALANCE * (1 - MAX_DAILY_LOSS_PCT) - 1.0)
    with pytest.raises(RiskViolation, match="halted"):
        risk.check_order("BTC/USD", 500.0, BALANCE, 0.0)


# --- Lot size spike guard ---

def test_lot_spike_guard_insufficient_history(risk: RiskEngine) -> None:
    risk.record_fill(0.1)
    risk.record_fill(0.1)
    # < 3 fills — no guard applied
    assert risk.check_lot_size(10.0) == 10.0


def test_lot_spike_guard_reduces_qty(risk: RiskEngine) -> None:
    for _ in range(5):
        risk.record_fill(0.1)
    # avg = 0.1, spike = 0.1 * 2 * 10 = way over
    result = risk.check_lot_size(1.0)
    assert result == pytest.approx(0.1)


def test_lot_within_bounds_unchanged(risk: RiskEngine) -> None:
    for _ in range(5):
        risk.record_fill(0.1)
    result = risk.check_lot_size(0.15)
    assert result == pytest.approx(0.15)


# --- Position sizer ---

def test_size_position(risk: RiskEngine) -> None:
    # 1% of $100k with 2% stop = $1000 / 0.02 = $50,000 notional
    notional = risk.size_position(BALANCE, stop_loss_pct=0.02)
    assert notional == pytest.approx(50_000.0)


def test_size_position_zero_stop_raises(risk: RiskEngine) -> None:
    with pytest.raises(ValueError):
        risk.size_position(BALANCE, stop_loss_pct=0.0)