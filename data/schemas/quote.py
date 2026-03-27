from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class Quote(BaseModel):
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    market: Literal["futures", "crypto"]
    source: Literal["alpaca", "ibkr"]

    @field_validator("bid", "ask", "bid_size", "ask_size")
    @classmethod
    def must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("quote fields must be non-negative")
        return v

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid
