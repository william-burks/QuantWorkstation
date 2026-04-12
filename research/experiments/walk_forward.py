"""
Walk-forward validation harness.

Splits bars into sequential train/test windows and runs a parameter sweep
on each train window. The best params from each sweep are then tested on
the corresponding out-of-sample test window.

This guards against overfitting — good params should generalise across
multiple unseen periods, not just look good in-sample.

Usage:
    from data.store import get_store
    from strategies.ema_crossover import EMACrossover
    from research.experiments.walk_forward import walk_forward

    bars = get_store().read_bars("crypto", "BTC/USD_daily")

    results = walk_forward(
        strategy_cls=EMACrossover,
        bars=bars,
        param_grid={"fast": [8, 12, 20], "slow": [21, 26, 50], "rsi_period": [14]},
        train_bars=365,
        test_bars=90,
    )
    print(results)
"""

import logging
from typing import Any

import pandas as pd

from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.adapters.vectorbt_adapter import run
from strategies.base import BaseStrategy

log = logging.getLogger(__name__)


def walk_forward(
    strategy_cls: type[BaseStrategy],
    bars: pd.DataFrame,
    param_grid: dict[str, list[Any]],
    train_bars: int = 365,
    test_bars: int = 90,
    init_cash: float = 100_000.0,
    fees: float = 0.001,
    freq: str = "1D",
    min_trades: int = 5,
    leverage: float = 5.0,
) -> pd.DataFrame:
    """
    Walk-forward validation.

    Parameters
    ----------
    strategy_cls : type[BaseStrategy]
    bars : pd.DataFrame
        Full OHLCV bar history.
    param_grid : dict
        Parameter grid for in-sample sweep.
    train_bars : int
        Number of bars in each training window.
    test_bars : int
        Number of bars in each out-of-sample test window.
    init_cash, fees, freq, min_trades
        Passed through to sweep and run.

    Returns
    -------
    pd.DataFrame
        One row per walk-forward window with best in-sample params,
        in-sample Sharpe, and out-of-sample metrics.
    """
    total = len(bars)
    step = test_bars
    start = train_bars
    rows = []
    window = 0

    while start + test_bars <= total:
        train = bars.iloc[start - train_bars : start]
        test = bars.iloc[start : start + test_bars]

        log.info(
            "Window %d: train %s→%s (%d bars), test %s→%s (%d bars)",
            window,
            train.index[0].date(),
            train.index[-1].date(),
            len(train),
            test.index[0].date(),
            test.index[-1].date(),
            len(test),
        )

        in_sample = sweep(
            strategy_cls,
            train,
            param_grid,
            init_cash=init_cash,
            fees=fees,
            freq=freq,
            min_trades=min_trades,
            leverage=leverage,
        )

        if in_sample.empty:
            log.warning("Window %d: no valid in-sample results, skipping", window)
            start += step
            window += 1
            continue

        best = in_sample.iloc[0]
        best_params = {k: best[k] for k in param_grid}

        strategy = strategy_cls(**best_params)
        pf = run(strategy, test, init_cash=init_cash, fees=fees, freq=freq, leverage=leverage)
        oos_metrics = summary(pf.value())

        rows.append(
            {
                "window": window,
                "train_start": train.index[0],
                "train_end": train.index[-1],
                "test_start": test.index[0],
                "test_end": test.index[-1],
                **{f"param_{k}": v for k, v in best_params.items()},
                "in_sample_sharpe": best["sharpe"],
                **{f"oos_{k}": v for k, v in oos_metrics.items()},
            }
        )

        start += step
        window += 1

    return pd.DataFrame(rows)
