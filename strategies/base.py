"""
BaseStrategy ABC.

All strategies inherit from this. Adapters (vectorbt, backtrader) call
generate_signals() and translate the output into engine-specific calls.
Strategies never import vectorbt or backtrader directly.
"""

from abc import ABC, abstractmethod
from typing import Literal

import pandas as pd


class BaseStrategy(ABC):
    #: Unique strategy identifier — used as key in arcticdb signals store
    name: str
    #: Markets this strategy is designed for
    markets: list[Literal["futures", "crypto"]]
    #: Strategy hyperparameters — set in __init__, used in generate_signals
    params: dict

    @abstractmethod
    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        """
        Compute directional signals from OHLCV bars.

        Parameters
        ----------
        bars : pd.DataFrame
            Columns: open, high, low, close, volume
            Index:   DatetimeIndex (UTC), one row per bar

        Returns
        -------
        pd.Series
            Same index as bars. Values: 1 (long), -1 (short), 0 (flat).
            Name should be set to self.name.
        """
        ...

    @abstractmethod
    def validate_params(self) -> bool:
        """Return True if params are valid, raise ValueError otherwise."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.params})"