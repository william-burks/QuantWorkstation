"""
RSI Reversion strategy with Bollinger Band confirmation.

Entry logic:
  Long  (1):  RSI < oversold AND close <= lower Bollinger band
  Short (-1): RSI > overbought AND close >= upper Bollinger band

Designed for 1H bars with a short max hold (6 bars). The expectation is
that price has stretched too far from mean and will snap back within hours.
Trade management (TP, SL, time exit) is handled by the vectorbt adapter.
"""

import pandas as pd

from strategies.base import BaseStrategy


class RSIReversion(BaseStrategy):
    name = "rsi_reversion"
    markets = ["crypto", "futures"]

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        bb_period: int = 20,
        bb_std: float = 2.0,
    ) -> None:
        self.params = {
            "rsi_period": rsi_period,
            "oversold": oversold,
            "overbought": overbought,
            "bb_period": bb_period,
            "bb_std": bb_std,
        }
        self.validate_params()

    def validate_params(self) -> bool:
        if not (0 < self.params["oversold"] < self.params["overbought"] < 100):
            raise ValueError("oversold < overbought, both in (0, 100)")
        if self.params["bb_period"] < 2:
            raise ValueError("bb_period must be >= 2")
        if self.params["bb_std"] <= 0:
            raise ValueError("bb_std must be > 0")
        return True

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]

        rsi = _rsi(close, self.params["rsi_period"])

        sma = close.rolling(self.params["bb_period"]).mean()
        std = close.rolling(self.params["bb_period"]).std()
        upper = sma + self.params["bb_std"] * std
        lower = sma - self.params["bb_std"] * std

        signals = pd.Series(0, index=bars.index, name=self.name)
        signals[(rsi < self.params["oversold"]) & (close <= lower)] = 1
        signals[(rsi > self.params["overbought"]) & (close >= upper)] = -1

        return signals


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))
