from typing import Literal

from pydantic import BaseModel, model_validator


class Order(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    qty: float | None = None       # mutually exclusive with notional
    notional: float | None = None  # USD value — mutually exclusive with qty
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = None
    reason: str = ""

    @model_validator(mode="after")
    def qty_or_notional(self) -> "Order":
        if (self.qty is None) == (self.notional is None):
            raise ValueError("exactly one of qty or notional must be set")
        return self