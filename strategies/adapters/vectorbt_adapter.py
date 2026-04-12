"""
vectorbt adapter for BaseStrategy.

Runs a strategy against a bar DataFrame and returns a vectorbt Portfolio.
The Portfolio exposes the full vectorbt API: stats(), plot(), trades, etc.

Usage:
    from data.store import get_store
    from strategies.rsi_reversion import RSIReversion
    from strategies.adapters.vectorbt_adapter import run

    bars = get_store().read_bars("crypto", "BTC/USD_1H")
    strategy = RSIReversion()
    pf = run(strategy, bars, freq="1H")
    print(pf.stats())
"""

import numpy as np
import pandas as pd
import vectorbt as vbt

from strategies.base import BaseStrategy


def run(
    strategy: BaseStrategy,
    bars: pd.DataFrame,
    init_cash: float = 100_000.0,
    fees: float = 0.001,  # 0.1% per trade — Alpaca crypto taker fee
    freq: str = "1H",
    leverage: float = 5.0,
    sl_stop: float = 0.008,  # 0.8% stop loss from entry
    tp_stop: float = 0.020,  # 2.0% take profit from entry
    time_stop: int = 6,  # exit after N bars regardless of signal
) -> "vbt.Portfolio":
    """
    Run a strategy backtest using vectorbt.

    Parameters
    ----------
    strategy : BaseStrategy
    bars : pd.DataFrame
        OHLCV bars with DatetimeIndex (UTC).
    init_cash : float
        Starting capital (actual margin).
    fees : float
        Per-trade fee fraction (0.1% = Alpaca crypto taker).
    freq : str
        Bar frequency for annualisation (e.g. "1H", "1D").
    leverage : float
        Position size multiplier (default 5x).
    sl_stop : float
        Stop loss as a fraction from entry price (0.008 = 0.8%).
    tp_stop : float
        Take profit as a fraction from entry price (0.02 = 2.0%).
    time_stop : int
        Force exit after this many bars if neither SL nor TP triggered.

    Returns
    -------
    vbt.Portfolio
        Equity starts at init_cash * leverage; use leveraged_to_margin()
        to re-anchor to actual margin for % return calculations.
    """
    signals = strategy.generate_signals(bars)
    # Shift by 1: signal computed at close of bar T executes at close of bar T+1.
    # Without this, entry uses the same close that generated the signal (lookahead bias).
    signals = signals.shift(1).fillna(0).astype(int)
    close = bars["close"]

    entries = (signals == 1).values
    short_entries = (signals == -1).values

    # Time-based exits: force close N bars after entry
    long_time_exits = _time_exits(entries, time_stop)
    short_time_exits = _time_exits(short_entries, time_stop)

    # Signal-based exits (opposite signal) combined with time exits
    long_exits = ((signals == -1) | pd.Series(long_time_exits, index=bars.index)).values
    short_exits = ((signals == 1) | pd.Series(short_time_exits, index=bars.index)).values

    return vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        init_cash=init_cash * leverage,
        fees=fees,
        freq=freq,
        sl_stop=sl_stop,
        tp_stop=tp_stop,
        # Break-even approximation: once up 1.2%, trail SL so worst case
        # is near entry. Not exact — full break-even trigger requires
        # custom order logic (future improvement).
    )


def leveraged_to_margin(pf: "vbt.Portfolio", init_cash: float, leverage: float) -> pd.Series:
    """
    Re-anchor equity curve from leveraged_cash base to actual margin.
    Use this when computing % returns and drawdowns.
    """
    return pf.value() - (init_cash * leverage) + init_cash


# --- Helpers ---


def _time_exits(entries: np.ndarray, n_bars: int) -> np.ndarray:
    """Generate exit signals exactly n_bars after each entry."""
    exits = np.zeros(len(entries), dtype=bool)
    last_entry = -1
    for i, is_entry in enumerate(entries):
        if is_entry:
            last_entry = i
        if last_entry >= 0 and i == last_entry + n_bars:
            exits[i] = True
            last_entry = -1
    return exits
