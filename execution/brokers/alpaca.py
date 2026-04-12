"""
Alpaca crypto broker client.

Wraps alpaca-py TradingClient for order submission, position queries, and account info.
Paper mode by default (ALPACA_BASE_URL=https://paper-api.alpaca.markets).
"""

import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.models import TradeAccount
from alpaca.trading.requests import MarketOrderRequest

from data.config import get_settings
from data.schemas.order import Order
from execution.types import AccountState, PositionState

log = logging.getLogger(__name__)


class AlpacaBroker:
    def __init__(self) -> None:
        s = get_settings()
        self._client = TradingClient(
            api_key=s.alpaca_api_key,
            secret_key=s.alpaca_api_secret,
            paper="paper" in s.alpaca_base_url,
        )

    def get_account(self) -> AccountState:
        acct = self._client.get_account()
        if not isinstance(acct, TradeAccount):
            raise TypeError(f"Expected TradeAccount, got {type(acct)}")
        return AccountState(
            equity=float(acct.equity or 0),
            cash=float(acct.cash or 0),
            buying_power=float(acct.buying_power or 0),
        )

    def get_positions(self) -> list[PositionState]:
        results = []
        for p in self._client.get_all_positions():
            if not isinstance(p, AlpacaPosition):
                raise TypeError(f"Expected Position, got {type(p)}")
            results.append(
                PositionState(
                    symbol=p.symbol,
                    qty=float(p.qty or 0),
                    avg_entry_price=float(p.avg_entry_price or 0),
                    market_value=float(p.market_value or 0),
                    unrealized_pnl=float(p.unrealized_pl or 0),
                )
            )
        return results

    def submit_order(self, order: Order) -> str:
        """Submit a market order. Returns the Alpaca order ID."""
        request = MarketOrderRequest(
            symbol=order.symbol,
            qty=order.qty,
            notional=order.notional,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
        )
        result = self._client.submit_order(request)
        if not isinstance(result, AlpacaOrder):
            raise TypeError(f"Expected Order, got {type(result)}")
        log.info(
            "Order submitted: %s %s qty=%s notional=%s id=%s",
            order.side,
            order.symbol,
            order.qty,
            order.notional,
            result.id,
        )
        return str(result.id)

    def cancel_all_orders(self) -> None:
        self._client.cancel_orders()
        log.info("All open orders cancelled")

    def close_all_positions(self) -> None:
        self._client.close_all_positions(cancel_orders=True)
        log.info("All positions closed")

    def close_position(self, symbol: str) -> None:
        self._client.close_position(symbol)
        log.info("Position closed: %s", symbol)
