# ---
# Experiment 1 — RSI Reversion Baseline (Futures CL 1H)
# Sweep RSI and Bollinger Band params. Does mean-reversion edge exist on crude oil?
# Fees ~$1 RT per micro (0.000005 fraction). No stacked leverage.
from data.store import get_store
from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.rsi_reversion import RSIReversion

INIT_CASH = 100_000.0

store = get_store()
bars = store.read_bars("futures", "CL_continuous_1H")
bars_5min = store.read_bars("futures", "CL_continuous_5min")

metadata = {
    "strategy":   "rsi_reversion",
    "symbol":     "CL_continuous_1H",
    "freq":       "1H",
    "leverage":   1.0,
    "fees":       0.000005,
    "time_stop":  8,
    "sl_stop":    0.006,
    "tp_stop":    0.015,
    "data_span":  (
        f"{bars_5min.index.min().strftime('%Y-%m-%d %H:%M')}"
        f" → {bars_5min.index.max().strftime('%Y-%m-%d %H:%M')}"
        f" ({len(bars_5min):,} 5min bars)"
    ),
}

bh_equity = bars["close"] / bars["close"].iloc[0] * INIT_CASH
bh = summary(bh_equity)

results = sweep(
    RSIReversion, bars,
    param_grid={
        "rsi_period": [7, 14, 21],
        "oversold":   [25, 30, 35],
        "overbought": [65, 70, 75],
        "bb_period":  [14, 20],
        "bb_std":     [1.5, 2.0, 2.5],
    },
    freq=metadata["freq"],
    leverage=metadata["leverage"],
    fees=metadata["fees"],
    sl_stop=metadata["sl_stop"],
    tp_stop=metadata["tp_stop"],
    time_stop=metadata["time_stop"],
)

results = evaluate(results, bh)
report(results, bh, metadata)
