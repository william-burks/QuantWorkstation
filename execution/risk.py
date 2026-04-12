"""
Prop-firm risk engine for crypto trading.

Implements 2026 crypto prop firm standard:
  - 5% max daily loss (kill-switch)
  - 10% trailing drawdown from high-water mark (kill-switch)
  - 5% max symbol exposure
  - 40% max total exposure
  - 1% risk per trade (dynamic lot sizer)
  - 2.5% daily profit ceiling (stop trading for day)
  - 30% consistency rule: best day < 30% of eval goal; otherwise compliance mode
  - Lot size spike guard: current lot ≤ 2× last-10-trades average

All state is in-memory. Resets on process restart.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

log = logging.getLogger(__name__)

# --- Hard constants (prop-firm standard) ---
MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_DRAWDOWN_PCT = 0.10
MAX_SYMBOL_EXPOSURE_PCT = 0.05
MAX_TOTAL_EXPOSURE_PCT = 0.40
RISK_PER_TRADE_PCT = 0.01
DAILY_PROFIT_CEILING_PCT = 0.025
CONSISTENCY_THRESHOLD = 0.30
LOT_SPIKE_FACTOR = 2.0
COMPLIANCE_LOT_FRACTION = 0.001  # 0.1% of equity in compliance mode


class TradingState(StrEnum):
    TRADING = "TRADING"
    DAILY_CAP_HIT = "DAILY_CAP_HIT"      # 2.5% profit reached — done for day
    DAILY_LOSS_HALT = "DAILY_LOSS_HALT"  # 5% daily loss breached — kill-switch
    DRAWDOWN_HALT = "DRAWDOWN_HALT"      # 10% trailing drawdown — kill-switch
    COMPLIANCE_MODE = "COMPLIANCE_MODE"  # best day > 30% of goal — min lots only


class RiskViolation(Exception):
    pass


@dataclass
class RiskEngine:
    eval_profit_target: float  # evaluation profit goal in USD (from config)

    _state: TradingState = field(default=TradingState.TRADING, init=False)
    _starting_day_balance: float = field(default=0.0, init=False)
    _high_water_mark: float = field(default=0.0, init=False)
    _best_day_pnl: float = field(default=0.0, init=False)
    _last_qtys: deque = field(default_factory=lambda: deque(maxlen=10), init=False)

    def seed(self, equity: float) -> None:
        """Initialize with current equity on process startup."""
        if self._starting_day_balance == 0.0:
            self._starting_day_balance = equity
        if self._high_water_mark == 0.0:
            self._high_water_mark = equity
        log.info("RiskEngine seeded: balance=%.2f hwm=%.2f target=%.2f",
                 self._starting_day_balance, self._high_water_mark, self.eval_profit_target)

    def reset_day(self, equity: float) -> None:
        """Call at UTC midnight. Locks in new starting balance, lifts daily halts."""
        self._high_water_mark = max(self._high_water_mark, equity)
        self._starting_day_balance = equity
        if self._state in (TradingState.DAILY_CAP_HIT, TradingState.DAILY_LOSS_HALT):
            self._state = TradingState.TRADING
            log.info("Day reset: state → TRADING, balance=%.2f", equity)

    def update(self, equity: float) -> TradingState:
        """
        Recompute state from latest equity snapshot.
        daily_pnl is computed as equity - starting_day_balance.
        Call after every fill and on a periodic heartbeat.
        """
        daily_pnl = equity - self._starting_day_balance

        # Update HWM before drawdown check
        if equity > self._high_water_mark:
            self._high_water_mark = equity

        # Kill-switches first (these don't lift until day reset / manual intervention)
        if equity <= self._high_water_mark * (1 - MAX_TOTAL_DRAWDOWN_PCT):
            self._transition(TradingState.DRAWDOWN_HALT,
                             "equity=%.2f hwm=%.2f", equity, self._high_water_mark)
            return self._state

        if daily_pnl <= -(self._starting_day_balance * MAX_DAILY_LOSS_PCT):
            self._transition(TradingState.DAILY_LOSS_HALT,
                             "daily_pnl=%.2f limit=%.2f",
                             daily_pnl, -(self._starting_day_balance * MAX_DAILY_LOSS_PCT))
            return self._state

        # Daily profit ceiling — done for day, not a hard halt
        if daily_pnl >= self._starting_day_balance * DAILY_PROFIT_CEILING_PCT:
            self._transition(TradingState.DAILY_CAP_HIT,
                             "daily_pnl=%.2f cap=%.2f",
                             daily_pnl, self._starting_day_balance * DAILY_PROFIT_CEILING_PCT)
            return self._state

        # Consistency rule — best day must be < 30% of eval goal
        if daily_pnl > self._best_day_pnl:
            self._best_day_pnl = daily_pnl

        consistency_limit = self.eval_profit_target * CONSISTENCY_THRESHOLD
        if self._best_day_pnl > consistency_limit:
            self._transition(TradingState.COMPLIANCE_MODE,
                             "best_day=%.2f limit=%.2f", self._best_day_pnl, consistency_limit)
        elif self._state == TradingState.COMPLIANCE_MODE:
            self._state = TradingState.TRADING

        return self._state

    def check_order(
        self,
        symbol: str,
        notional: float,
        account_equity: float,
        total_exposure_notional: float,
    ) -> float:
        """
        Validate and cap a proposed order notional.
        Returns approved notional (may be reduced by exposure caps).
        Raises RiskViolation if the order cannot be placed at all.
        """
        if self._state in (TradingState.DAILY_LOSS_HALT, TradingState.DRAWDOWN_HALT):
            raise RiskViolation(f"Trading halted: {self._state.value}")

        if self._state == TradingState.DAILY_CAP_HIT:
            raise RiskViolation("Daily profit cap reached — no new entries until UTC midnight")

        # Per-symbol cap
        symbol_cap = account_equity * MAX_SYMBOL_EXPOSURE_PCT
        if notional > symbol_cap:
            log.warning("Symbol cap: %s %.2f → %.2f", symbol, notional, symbol_cap)
            notional = symbol_cap

        # Total exposure cap
        remaining = (account_equity * MAX_TOTAL_EXPOSURE_PCT) - total_exposure_notional
        if remaining <= 0:
            raise RiskViolation("Total exposure cap reached (40% of account)")
        if notional > remaining:
            log.warning("Total exposure cap: %.2f → %.2f", notional, remaining)
            notional = remaining

        # Compliance mode: reduce to minimum lot size
        if self._state == TradingState.COMPLIANCE_MODE:
            compliance_cap = account_equity * COMPLIANCE_LOT_FRACTION
            notional = min(notional, compliance_cap)
            log.info("Compliance mode active: notional capped at %.2f", notional)

        return notional

    def size_position(self, account_balance: float, stop_loss_pct: float) -> float:
        """
        Dynamic lot sizer using RISK_PER_TRADE_PCT.
        stop_loss_pct: fraction of price to stop (e.g. 0.02 = 2% stop).
        Returns notional position size in USD.
        """
        if stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be > 0")
        return (account_balance * RISK_PER_TRADE_PCT) / stop_loss_pct

    def record_fill(self, qty: float) -> None:
        """Record fill qty for lot-size spike tracking."""
        self._last_qtys.append(abs(qty))

    def check_lot_size(self, qty: float) -> float:
        """
        Guard against lot size spikes.
        If qty > 2× last-10-trades average, reduces to the average.
        """
        if len(self._last_qtys) < 3:
            return qty
        avg = sum(self._last_qtys) / len(self._last_qtys)
        if qty > avg * LOT_SPIKE_FACTOR:
            log.warning("Lot spike: %.6f → %.6f (avg=%.6f)", qty, avg, avg)
            return avg
        return qty

    @property
    def state(self) -> TradingState:
        return self._state

    def is_halted(self) -> bool:
        return self._state in (TradingState.DAILY_LOSS_HALT, TradingState.DRAWDOWN_HALT)

    def get_status(self) -> dict:
        return {
            "state": self._state.value,
            "starting_day_balance": self._starting_day_balance,
            "high_water_mark": self._high_water_mark,
            "best_day_pnl": self._best_day_pnl,
            "eval_profit_target": self.eval_profit_target,
            "consistency_limit": self.eval_profit_target * CONSISTENCY_THRESHOLD,
        }

    def _transition(self, new_state: TradingState, msg: str, *args: object) -> None:
        if self._state != new_state:
            log.warning("Risk state %s → %s: " + msg, self._state.value, new_state.value, *args)
            self._state = new_state