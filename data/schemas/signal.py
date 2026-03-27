from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class Signal(BaseModel):
    strategy: str
    symbol: str
    timestamp: datetime
    direction: Literal["long", "short", "flat"]
    strength: float              # 0.0–1.0
    params: dict[str, Any] = {} # strategy params that generated this signal

    @field_validator("strength")
    @classmethod
    def strength_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("strength must be between 0.0 and 1.0")
        return v
