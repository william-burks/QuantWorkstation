"""Shared broker types — used by both AlpacaBroker and IBKRBroker."""

from dataclasses import dataclass


@dataclass
class AccountState:
    equity: float  # total account value / net liquidation
    cash: float  # cash / total cash value
    buying_power: float  # available funds


@dataclass
class PositionState:
    symbol: str
    qty: float  # contracts (futures) or units (crypto); negative = short
    avg_entry_price: float
    market_value: float
    unrealized_pnl: float
