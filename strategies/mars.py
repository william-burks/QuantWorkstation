"""
MARS — Momentum + Allocation + Rebalancing + Screening.

Signal logic:
  - Momentum score: rate-of-change over `mom_period` bars
  - Trend filter:   close > SMA(trend_period) → only take longs
  - Volatility screen: skip bars where ATR/close > vol_threshold (avoid whipsaw)
  - Signal:  1 if momentum > 0 and trend filter passes and vol screen passes
            -1 if momentum < 0 and trend filter fails (close < SMA)
             0 otherwise

Designed for daily crypto bars. MARS is a position-sizing strategy — use
size_position() from the RiskEngine to convert the signal into a notional.
"""

import pandas as pd

from strategies.base import BaseStrategy


class MARS(BaseStrategy):
    name = "mars"
    markets = ["crypto"]

    def __init__(
        self,
        mom_period: int = 20,
        trend_period: int = 50,
        atr_period: int = 14,
        vol_threshold: float = 0.05,  # ATR/close > 5% = too volatile
    ) -> None:
        self.params = {
            "mom_period": mom_period,
            "trend_period": trend_period,
            "atr_period": atr_period,
            "vol_threshold": vol_threshold,
        }
        self.validate_params()

    def validate_params(self) -> bool:
        if self.params["mom_period"] < 2:
            raise ValueError("mom_period must be >= 2")
        if self.params["trend_period"] < self.params["mom_period"]:
            raise ValueError("trend_period must be >= mom_period")
        if not (0 < self.params["vol_threshold"] < 1):
            raise ValueError("vol_threshold must be in (0, 1)")
        return True

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]
        high = bars["high"]
        low = bars["low"]

        momentum = close.pct_change(self.params["mom_period"])
        sma = close.rolling(self.params["trend_period"]).mean()
        atr = _atr(high, low, close, self.params["atr_period"])
        relative_vol = atr / close

        trend_up = close > sma
        low_vol = relative_vol < self.params["vol_threshold"]

        signals = pd.Series(0, index=bars.index, name=self.name)
        signals[(momentum > 0) & trend_up & low_vol] = 1
        signals[(momentum < 0) & ~trend_up] = -1

        return signals


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()
