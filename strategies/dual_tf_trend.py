"""
Dual-timeframe trend following strategy.

Higher timeframe (4H, derived by resampling) sets directional bias via EMA crossover.
Lower timeframe (1H, execution) provides entry timing via EMA crossover.

Entry logic:
  Long  (1):  4H fast EMA > 4H slow EMA (bullish bias)
              AND 1H fast EMA crosses above 1H slow EMA
  Short (-1): 4H fast EMA < 4H slow EMA (bearish bias)
              AND 1H fast EMA crosses below 1H slow EMA

Position is carried forward until:
  - Opposite 1H EMA cross
  - 4H bias flips against the position

The 4H bias is computed by resampling input bars internally — no separate
4H feed required. Forward-fill ensures no lookahead: only the last
completed 4H bar's EMA value is visible at each 1H timestamp.
"""

import pandas as pd

from strategies.base import BaseStrategy


class DualTFTrend(BaseStrategy):
    name = "dual_tf_trend"
    markets = ["futures"]

    def __init__(
        self,
        ltf_fast: int = 12,
        ltf_slow: int = 26,
        htf_fast: int = 8,
        htf_slow: int = 21,
    ) -> None:
        self.params = {
            "ltf_fast": ltf_fast,
            "ltf_slow": ltf_slow,
            "htf_fast": htf_fast,
            "htf_slow": htf_slow,
        }
        self.validate_params()

    def validate_params(self) -> bool:
        if self.params["ltf_fast"] >= self.params["ltf_slow"]:
            raise ValueError("ltf_fast must be < ltf_slow")
        if self.params["htf_fast"] >= self.params["htf_slow"]:
            raise ValueError("htf_fast must be < htf_slow")
        return True

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]

        # --- 4H bias: resample input bars, forward-fill to execution timeframe ---
        htf = bars.resample("4h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna(subset=["close"])

        htf_ema_fast = htf["close"].ewm(span=self.params["htf_fast"], adjust=False).mean()
        htf_ema_slow = htf["close"].ewm(span=self.params["htf_slow"], adjust=False).mean()

        # Forward-fill: each 1H bar sees only the last completed 4H bar's value
        htf_bull = (htf_ema_fast > htf_ema_slow).reindex(bars.index, method="ffill").fillna(False)
        htf_bear = (htf_ema_fast < htf_ema_slow).reindex(bars.index, method="ffill").fillna(False)

        # --- 1H entry: EMA crossover ---
        ltf_ema_fast = close.ewm(span=self.params["ltf_fast"], adjust=False).mean()
        ltf_ema_slow = close.ewm(span=self.params["ltf_slow"], adjust=False).mean()

        cross_up = (ltf_ema_fast > ltf_ema_slow) & (ltf_ema_fast.shift(1) <= ltf_ema_slow.shift(1))
        cross_down = (ltf_ema_fast < ltf_ema_slow) & (ltf_ema_fast.shift(1) >= ltf_ema_slow.shift(1))

        # --- State machine: carry position until exit condition ---
        signals = pd.Series(0, index=bars.index, name=self.name)
        position = 0
        for i in range(len(bars)):
            # Exit: bias flipped or opposite cross
            if position == 1 and (cross_down.iloc[i] or htf_bear.iloc[i]):
                position = 0
            elif position == -1 and (cross_up.iloc[i] or htf_bull.iloc[i]):
                position = 0

            # Enter: bias and cross aligned
            if position == 0:
                if htf_bull.iloc[i] and cross_up.iloc[i]:
                    position = 1
                elif htf_bear.iloc[i] and cross_down.iloc[i]:
                    position = -1

            signals.iloc[i] = position

        return signals
