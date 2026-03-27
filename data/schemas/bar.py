from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class Bar(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    market: Literal["futures", "crypto"]
    source: Literal["alpaca", "ibkr"]
    adjusted: bool = False  # True for roll-adjusted futures continuous series

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("price/volume fields must be non-negative")
        return v

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v: float, info: object) -> float:
        # info.data only has fields validated before this one
        low = getattr(info, "data", {}).get("low")
        if low is not None and v < low:
            raise ValueError("high must be >= low")
        return v
