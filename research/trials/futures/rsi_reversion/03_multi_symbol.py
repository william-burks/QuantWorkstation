# ---
# Experiment 3 — Multi-Symbol (Futures RSI Reversion)
# Use best timeframe from 02 and best params from 01.
# Question: do the same RSI/BB params generalise across MES, MNQ, MGC, CL?
# Report back: Per-symbol Sharpe and drawdown. Flag any symbol where it breaks.
from data.store import get_store
from research.experiments.sweep import sweep
from strategies.rsi_reversion import RSIReversion

store = get_store()

# Fill in after running 01 and 02
BEST_TF = "1H"
BEST_FREQ = "1H"
BEST_TIME_STOP = 8
BEST_SL = 0.004
BEST_TP = 0.012

BEST_PARAMS = {
    "rsi_period": [14],
    "oversold": [30],
    "overbought": [70],
    "bb_period": [20],
    "bb_std": [2.0],
}

symbols = [
    f"MES_continuous_{BEST_TF}",
    f"MNQ_continuous_{BEST_TF}",
    f"MGC_continuous_{BEST_TF}",
    f"CL_continuous_{BEST_TF}",
]

cols = ["sharpe", "max_drawdown", "return", "fees", "win_rate", "n_trades"]

for symbol in symbols:
    bars = store.read_bars("futures", symbol)
    results = sweep(
        RSIReversion, bars,
        param_grid=BEST_PARAMS,
        freq=BEST_FREQ,
        leverage=1.0,
        fees=0.0001,
        sl_stop=BEST_SL,
        tp_stop=BEST_TP,
        time_stop=BEST_TIME_STOP,
    )
    print(f"\n--- {symbol} ---")
    if results.empty:
        print("No valid results")
    else:
        print(results[cols].head(3))
