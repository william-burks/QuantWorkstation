# research/trials/rsi_reversion/01_sweep.py
from data.store import get_store
from strategies.rsi_reversion import RSIReversion
from research.experiments.sweep import sweep

bars = get_store().read_bars("crypto", "BTC/USD_1H")

metadata = {
    "freq": "1H",
    "leverage": 1.0,
    "time_stop": 6,
    "sl_stop": 0.008,
    "tp_stop": 0.020
}

results = sweep(
    RSIReversion, bars,
    param_grid={
        "rsi_period": [7, 14, 21],
        "oversold": [25, 30],
        "overbought": [70, 75],
        "bb_period": [14, 20],
        "bb_std": [1.5, 2.0, 2.5],
    },
    freq=metadata["freq"],
    leverage=metadata["leverage"],
    sl_stop=metadata["sl_stop"],
    tp_stop=metadata["tp_stop"],
    time_stop=metadata["time_stop"],
)

print("\n" + "="*10 + " METADATA " + "="*10)
for key, value in metadata.items():
    print(f"{key.upper()}: {value}")

print("\n" + "="*10 + " TOP 10 RESULTS " + "="*10)
# Ensure columns exist before printing to avoid KeyErrors
cols_to_print = [
    "rsi_period", "oversold", "overbought", "bb_period", "bb_std",
    "sharpe", "max_drawdown", "return", "gain",
    "fees", "win_rate", "n_trades"
]
print(results[cols_to_print].head(10))