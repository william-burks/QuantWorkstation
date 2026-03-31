# ---
# Experiment 2 — MARS Sweep
# MARS has a volatility screen — test if it controls drawdown better.
# Report back: Best 3 rows by Sharpe, and whether any have max_drawdown > -0.50.
from data import get_store
from research.experiments.sweep import sweep
from strategies.mars import MARS

bars = get_store().read_bars("crypto", "BTC/USD_1D")

results = sweep(
    MARS, bars,
    param_grid={
        "mom_period": [10, 20, 30],
        "trend_period": [50, 100, 200],
        "atr_period": [14],
        "vol_threshold": [0.03, 0.05, 0.08],
    },
    leverage=5.0,
)
print(results[["mom_period", "trend_period", "vol_threshold", "sharpe", "max_drawdown", "return", "n_trades"]])
