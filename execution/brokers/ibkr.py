"""
IBKR futures broker client via ib_insync.

Requires IB Gateway or TWS running before instantiation.
  Paper: port 4002
  Live:  port 4001

Usage:
    broker = IBKRBroker()
    broker.connect()
    acct = broker.get_account()
    positions = broker.get_positions()
    broker.submit_order(Order(symbol="MES", side="buy", qty=1))
    broker.disconnect()

Or as a context manager:
    with IBKRBroker() as broker:
        orders = oms.rebalance(targets, broker.get_positions(), broker.get_account().equity)
        for order in orders:
            broker.submit_order(order)
"""

import logging

from ib_insync import IB, Contract, MarketOrder

from data.config import get_settings
from data.schemas.order import Order
from execution.types import AccountState, PositionState

log = logging.getLogger(__name__)

# Contract specs for supported futures roots
# Add micro contracts (MES, MNQ) for lower margin requirements
_CONTRACT_SPECS: dict[str, dict] = {
    "MES": {"multiplier": "5",    "exchange": "CME",   "currency": "USD"},
    "MNQ": {"multiplier": "2",    "exchange": "CME",   "currency": "USD"},
    "MGC": {"multiplier": "10",   "exchange": "COMEX", "currency": "USD"},
    "CL":  {"multiplier": "1000", "exchange": "NYMEX", "currency": "USD"},
    "ES":  {"multiplier": "50",   "exchange": "CME",   "currency": "USD"},
    "NQ":  {"multiplier": "20",   "exchange": "CME",   "currency": "USD"},
    "GC":  {"multiplier": "100",  "exchange": "COMEX", "currency": "USD"},
    "RTY": {"multiplier": "50",   "exchange": "CME",   "currency": "USD"},
    "M2K": {"multiplier": "5",    "exchange": "CME",   "currency": "USD"},
}


class IBKRBroker:
    def __init__(self) -> None:
        s = get_settings()
        self._host = s.ibkr_host
        self._port = s.ibkr_port
        self._client_id = s.ibkr_client_id
        self._ib = IB()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._ib.isConnected():
            return
        self._ib.connect(self._host, self._port, clientId=self._client_id)
        log.info("IBKR connected: %s:%d clientId=%d", self._host, self._port, self._client_id)

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()
            log.info("IBKR disconnected")

    def __enter__(self) -> "IBKRBroker":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> AccountState:
        summary = {item.tag: item.value for item in self._ib.accountSummary()}
        return AccountState(
            equity=float(summary.get("NetLiquidation", 0)),
            cash=float(summary.get("TotalCashValue", 0)),
            buying_power=float(summary.get("AvailableFunds", 0)),
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[PositionState]:
        return [
            PositionState(
                symbol=item.contract.symbol,
                qty=float(item.position),
                avg_entry_price=float(item.averageCost),
                market_value=float(item.marketValue),
                unrealized_pnl=float(item.unrealizedPNL),
            )
            for item in self._ib.portfolio()
            if item.contract.secType == "FUT" and item.position != 0
        ]

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        """
        Submit a market order. qty must be set (futures are sized in contracts).
        Returns the IBKR order ID.
        """
        if order.qty is None:
            raise ValueError("IBKR orders require qty (number of contracts), not notional")

        contract = self._resolve_contract(order.symbol)
        ib_order = MarketOrder(
            action="BUY" if order.side == "buy" else "SELL",
            totalQuantity=abs(int(order.qty)),
        )
        trade = self._ib.placeOrder(contract, ib_order)
        self._ib.sleep(0)  # yield to event loop so order is registered
        log.info(
            "Order placed: %s %s qty=%d id=%s",
            order.side, order.symbol, order.qty, trade.order.orderId,
        )
        return str(trade.order.orderId)

    def cancel_all_orders(self) -> None:
        for trade in self._ib.openTrades():
            self._ib.cancelOrder(trade.order)
        log.info("All open orders cancelled")

    def close_all_positions(self) -> None:
        for pos in self.get_positions():
            if pos.qty == 0:
                continue
            side = "sell" if pos.qty > 0 else "buy"
            self.submit_order(
                Order(symbol=pos.symbol, side=side, qty=abs(pos.qty), reason="close_all")
            )
        log.info("All positions closed")

    def close_position(self, symbol: str) -> None:
        for pos in self.get_positions():
            if pos.symbol == symbol and pos.qty != 0:
                side = "sell" if pos.qty > 0 else "buy"
                self.submit_order(Order(symbol=symbol, side=side, qty=abs(pos.qty), reason="close"))
                return
        log.warning("close_position: no open position for %s", symbol)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_contract(self, root: str) -> Contract:
        """Qualify and return the front-month contract for a root symbol."""
        if root not in _CONTRACT_SPECS:
            raise ValueError(f"Unknown futures root '{root}'. Add it to _CONTRACT_SPECS.")
        spec = _CONTRACT_SPECS[root]
        contract = Contract(
            symbol=root,
            secType="FUT",
            exchange=spec["exchange"],
            currency=spec["currency"],
        )
        details = self._ib.reqContractDetails(contract)
        if not details:
            raise ValueError(f"No contract details returned for {root} — is IB Gateway running?")
        # reqContractDetails returns all expiries sorted ascending — first = front month
        return details[0].contract

    def notional_to_qty(self, symbol: str, price: float, notional: float) -> int:
        """
        Convert a notional USD amount to number of contracts.
        Rounds down — never exceeds intended notional.
        """
        spec = _CONTRACT_SPECS[symbol]
        contract_value = price * float(spec["multiplier"])
        return max(1, int(notional / contract_value))
