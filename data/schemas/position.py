from typing import Literal

from pydantic import BaseModel


class Position(BaseModel):
    symbol: str
    market: Literal["futures", "crypto"]
    qty: float                   # positive = long, negative = short
    avg_price: float
    unrealized_pnl: float
    broker: Literal["alpaca", "ibkr"]
