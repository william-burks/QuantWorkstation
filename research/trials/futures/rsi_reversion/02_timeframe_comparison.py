# ---
# Experiment 2 — Timeframe Comparison (Futures RSI Reversion)
# Use best params from 01_sweep. Does 15min outperform 1H?
# All timeframes normalized to the same start date so metrics are comparable.
# Use Sharpe tier assessment instead of cross-timeframe BH comparison.
import pandas as pd

from data.store import get_store
from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.rsi_reversion import RSIReversion

# Earliest common bar across all timeframes
COMMON_START = pd.Timestamp("2024-01-21", tz="UTC")

store = get_store()

# Best params from 01_sweep (top result: Sharpe 0.330 on CL 1H)
BEST_PARAMS = {
    "rsi_period": [7],
    "oversold":   [35],
    "overbought": [70],
    "bb_period":  [20],
    "bb_std":     [1.5],
}

timeframes = [
    # (symbol, freq, time_stop, sl_stop, tp_stop)
    ("CL_continuous_15min", "15T", 16, 0.006, 0.015),
    ("CL_continuous_1H",    "1H",   8, 0.006, 0.015),
]

for symbol, freq, time_stop, sl_stop, tp_stop in timeframes:
    bars = store.read_bars("futures", symbol, start=COMMON_START)

    bh_equity = bars["close"] / bars["close"].iloc[0] * 100_000
    bh = summary(bh_equity)

    results = sweep(
        RSIReversion, bars,
        param_grid=BEST_PARAMS,
        freq=freq,
        leverage=1.0,
        fees=0.000005,
        sl_stop=sl_stop,
        tp_stop=tp_stop,
        time_stop=time_stop,
    )

    metadata = {
        "strategy":  "rsi_reversion",
        "symbol":    symbol,
        "freq":      freq,
        "leverage":  1.0,
        "fees":      0.000005,
        "sl_stop":   sl_stop,
        "tp_stop":   tp_stop,
        "time_stop": time_stop,
        "data_span": f"from {COMMON_START.date()} ({len(bars):,} bars)",
    }

    if results.empty:
        print(f"\n{symbol}: no valid results")
        continue

    results = evaluate(results, bh)
    report(results, bh, metadata, top_n=1, full_n=3)
