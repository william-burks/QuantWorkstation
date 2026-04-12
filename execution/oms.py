"""
Order Management System (OMS).

Converts target positions (symbol → notional USD) into a list of Orders,
running each through the RiskEngine before returning.

Usage:
    oms = OMS(risk_engine)
    orders = oms.rebalance(
        targets={"BTC/USD": 5000.0, "ETH/USD": 2000.0},
        current=broker.get_positions(),
        account_equity=broker.get_account().equity,
    )
    for order in orders:
        broker.submit_order(order)
"""

import logging
from typing import Literal

from data.schemas.order import Order
from execution.risk import RiskEngine, RiskViolation
from execution.types import PositionState

log = logging.getLogger(__name__)

_MIN_NOTIONAL = 1.0  # ignore deltas smaller than $1


class OMS:
    def __init__(self, risk: RiskEngine) -> None:
        self._risk = risk

    def rebalance(
        self,
        targets: dict[str, float],  # symbol → target notional USD (0 = close)
        current: list[PositionState],
        account_equity: float,
    ) -> list[Order]:
        """
        Compute the minimal set of orders to move from current to target positions.
        Orders that fail risk checks are logged and skipped (not raised).
        """
        current_map = {p.symbol: p for p in current}
        total_exposure = sum(p.market_value for p in current)
        orders: list[Order] = []

        # Close positions absent from targets or with target=0
        for symbol, pos in current_map.items():
            if targets.get(symbol, 0) <= 0:
                orders.append(Order(symbol=symbol, side="sell", qty=pos.qty, reason="target=0"))
                log.info("OMS close: %s qty=%.6f", symbol, pos.qty)

        # Open or adjust positions in targets
        for symbol, target_notional in targets.items():
            if target_notional <= 0:
                continue

            current_notional = current_map[symbol].market_value if symbol in current_map else 0.0
            delta = target_notional - current_notional

            if abs(delta) < _MIN_NOTIONAL:
                continue

            try:
                approved = self._risk.check_order(
                    symbol=symbol,
                    notional=abs(delta),
                    account_equity=account_equity,
                    total_exposure_notional=total_exposure,
                )
            except RiskViolation as exc:
                log.warning("OMS blocked by risk: %s delta=%.2f — %s", symbol, delta, exc)
                continue

            side: Literal["buy", "sell"] = "buy" if delta > 0 else "sell"
            orders.append(Order(symbol=symbol, side=side, notional=approved, reason="rebalance"))
            log.info("OMS order: %s %s notional=%.2f", side, symbol, approved)

        return orders
