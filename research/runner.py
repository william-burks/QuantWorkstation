from data.store import get_store
from strategies.ema_crossover import EMACrossover
from research.experiments.sweep import sweep

bars = get_store().read_bars("crypto", "BTC/USD_1D")
results = sweep(EMACrossover, bars, {"fast": [8, 12, 20], "slow": [21, 26, 50], "rsi_period": [14]})
print(results.head())

