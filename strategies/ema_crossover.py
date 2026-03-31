"""
EMA Crossover strategy with RSI filter.

Signal logic:
  - Long  (1)  when fast EMA crosses above slow EMA AND RSI < rsi_overbought
  - Short (-1) when fast EMA crosses below slow EMA AND RSI > rsi_oversold
  - Flat  (0)  otherwise

Default params are a reasonable starting point for crypto daily bars.
Run a sweep to find optimal values for your target symbol.
"""

import pandas as pd

from strategies.base import BaseStrategy


class EMACrossover(BaseStrategy):
    name = "ema_crossover"
    markets = ["crypto", "futures"]

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ) -> None:
        self.params = {
            "fast": fast,
            "slow": slow,
            "rsi_period": rsi_period,
            "rsi_overbought": rsi_overbought,
            "rsi_oversold": rsi_oversold,
        }
        self.validate_params()

    def validate_params(self) -> bool:
        if self.params["fast"] >= self.params["slow"]:
            raise ValueError("fast must be < slow")
        if not (0 < self.params["rsi_period"]):
            raise ValueError("rsi_period must be > 0")
        if not (0 < self.params["rsi_oversold"] < self.params["rsi_overbought"] < 100):
            raise ValueError("rsi_oversold < rsi_overbought, both in (0, 100)")
        return True

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]
        fast = self.params["fast"]
        slow = self.params["slow"]
        period = self.params["rsi_period"]

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        rsi = _rsi(close, period)

        cross_up = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_down = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        signals = pd.Series(0, index=bars.index, name=self.name)

        # Carry forward position until the opposite cross
        position = 0
        for i in range(len(bars)):
            if cross_up.iloc[i] and rsi.iloc[i] < self.params["rsi_overbought"]:
                position = 1
            elif cross_down.iloc[i] and rsi.iloc[i] > self.params["rsi_oversold"]:
                position = -1
            signals.iloc[i] = position

        return signals


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))
