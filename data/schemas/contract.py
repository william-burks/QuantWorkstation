from datetime import date

from pydantic import BaseModel, field_validator


class FuturesContract(BaseModel):
    symbol: str                  # e.g. "ES"
    expiry: date
    multiplier: float            # e.g. 50.0 for ES ($ per point)
    margin: float                # initial margin requirement in USD
    front_month: bool
    continuous_symbol: str       # e.g. "ES_continuous"
    exchange: str = "CME"

    @field_validator("multiplier", "margin")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("multiplier and margin must be positive")
        return v
