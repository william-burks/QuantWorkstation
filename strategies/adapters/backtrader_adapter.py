"""
backtrader adapter for BaseStrategy.

Wraps a BaseStrategy in a backtrader Strategy subclass so it can be run
through backtrader's execution simulation engine (realistic fills, slippage,
commission modelling).

Usage:
    from data.store import get_store
    from strategies.ema_crossover import EMACrossover
    from strategies.adapters.backtrader_adapter import run

    bars = get_store().read_bars("crypto", "BTC/USD_daily")
    strategy = EMACrossover(fast=12, slow=26)
    result = run(strategy, bars, init_cash=10_000)
    print(result)
"""

import backtrader as bt
import pandas as pd

from strategies.base import BaseStrategy


class _BTStrategy(bt.Strategy):
    """Internal backtrader Strategy that replays pre-computed signals."""

    params = (("signals", None), ("leverage", 5.0))  # type: ignore[assignment]

    def __init__(self) -> None:
        self._signals: pd.Series = self.params.signals  # type: ignore[attr-defined]
        self._leverage: float = self.params.leverage  # type: ignore[attr-defined]
        self._idx = 0

    def next(self) -> None:
        if self._idx >= len(self._signals):
            return

        signal = self._signals.iloc[self._idx]
        self._idx += 1

        position = self.getposition().size
        target = 0.95 * self._leverage  # e.g. 5x → target 475% of cash

        if signal == 1 and position <= 0:
            self.order_target_percent(target=target)
        elif signal == -1 and position >= 0:
            self.order_target_percent(target=-target)
        elif signal == 0 and position != 0:
            self.order_target_percent(target=0.0)


def run(
    strategy: BaseStrategy,
    bars: pd.DataFrame,
    init_cash: float = 10_000.0,
    commission: float = 0.001,  # 0.1% per trade
    slippage: float = 0.001,  # 0.1% slippage model
    leverage: float = 5.0,
) -> dict:
    """
    Run a strategy through backtrader's execution simulation.

    Parameters
    ----------
    strategy : BaseStrategy
    bars : pd.DataFrame
        OHLCV bars with DatetimeIndex (UTC).
    init_cash : float
        Starting capital in USD.
    commission : float
        Per-trade commission fraction.
    slippage : float
        Slippage fraction applied to fill prices.

    Returns
    -------
    dict
        final_value, total_return, n_trades
    """
    signals = strategy.generate_signals(bars)

    # backtrader needs a specific DataFrame column layout
    bt_data = bt.feeds.PandasData(
        dataname=bars.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        ),
        openinterest=-1,
    )

    cerebro = bt.Cerebro()
    cerebro.adddata(bt_data)
    cerebro.addstrategy(_BTStrategy, signals=signals, leverage=leverage)
    cerebro.broker.setcash(init_cash)
    cerebro.broker.setcommission(commission=commission, leverage=leverage)
    cerebro.broker.set_slippage_perc(slippage)

    cerebro.run()

    final_value = cerebro.broker.getvalue()
    return {
        "init_cash": init_cash,
        "final_value": final_value,
        "total_return": (final_value / init_cash) - 1,
        "n_trades": len(cerebro.runstrats[0][0].stats.trades),
    }
