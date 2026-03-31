"""
Parameter sweep harness using vectorbt.

Runs a strategy across all combinations of param ranges and returns a
DataFrame of performance metrics ranked by Sharpe ratio.

Usage:
    from data.store import get_store
    from strategies.ema_crossover import EMACrossover
    from research.experiments.sweep import sweep

    bars = get_store().read_bars("crypto", "BTC/USD_daily")

    results = sweep(
        strategy_cls=EMACrossover,
        bars=bars,
        param_grid={
            "fast": [8, 12, 20],
            "slow": [21, 26, 50],
            "rsi_period": [14],
        },
        init_cash=10_000,
    )
    print(results.head(10))
"""

import itertools
import logging
from typing import Any

import pandas as pd

from research.experiments.metrics import summary
from strategies.adapters.vectorbt_adapter import leveraged_to_margin, run
from strategies.base import BaseStrategy

log = logging.getLogger(__name__)


def sweep(
    strategy_cls: type[BaseStrategy],
    bars: pd.DataFrame,
    param_grid: dict[str, list[Any]],
    init_cash: float = 100_000.0,
    fees: float = 0.001,
    freq: str = "1H",
    min_trades: int = 5,
    leverage: float = 5.0,
    sl_stop: float = 0.008,
    tp_stop: float = 0.020,
    time_stop: int = 6,
) -> pd.DataFrame:
    """
    Exhaustive grid search over param_grid.

    Parameters
    ----------
    strategy_cls : type[BaseStrategy]
        Strategy class (not instance) to instantiate for each combo.
    bars : pd.DataFrame
        OHLCV bars. Same bars used for all combinations.
    param_grid : dict[str, list]
        Keys are strategy __init__ parameter names; values are lists to iterate.
    init_cash : float
        Starting capital per run.
    fees : float
        Per-trade fee fraction.
    freq : str
        Bar frequency for vectorbt annualisation.
    min_trades : int
        Skip results with fewer than this many trades (avoids overfit single-trade wins).

    Returns
    -------
    pd.DataFrame
        One row per valid param combo, columns = params + metrics, sorted by Sharpe desc.
    """
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    log.info("Sweep: %d combinations × %d bars", len(combos), len(bars))

    rows = []
    for values in combos:
        params = dict(zip(keys, values))
        try:
            strategy = strategy_cls(**params)
        except ValueError:
            continue  # invalid param combo (e.g. fast >= slow)

        try:
            pf = run(
                strategy, bars,
                init_cash=init_cash, fees=fees, freq=freq,
                leverage=leverage, sl_stop=sl_stop, tp_stop=tp_stop, time_stop=time_stop,
            )
        except Exception as exc:
            log.warning("Combo %s failed: %s", params, exc)
            continue

        n_trades = int(pf.trades.count())
        if n_trades < min_trades:
            continue

        equity = leveraged_to_margin(pf, init_cash, leverage)
        trade_pnl = pd.Series(pf.trades.pnl.values)
        m = summary(equity, trade_pnl)

        gain = m["return"] * init_cash
        # Fees are paid on leveraged notional; this is an upper bound
        # (assumes full position size throughout — declines as account depletes)
        fees_dollar = n_trades * 2 * fees * init_cash * leverage

        rows.append({
            **params, **m,
            "n_trades": n_trades,
            "gain": round(gain, 2),
            "fees": round(fees_dollar, 2),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("sharpe", ascending=False).reset_index(drop=True)
    return df
