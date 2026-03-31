# ---
# Experiment 1 — EMA Crossover Baseline
# Establish what the best EMA params actually look like out - of - sample.
# Report back: Do the best in-sample params hold up OOS? Does any window show oos_max_drawdown > -0.50?
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from research.experiments.walk_forward import walk_forward
from strategies.adapters.vectorbt_adapter import run
from strategies.ema_crossover import EMACrossover
from data.store import get_store


for sym in ["BTC/USD_1D", "ETH/USD_1D"]:
    bars = get_store().read_bars("crypto", sym)
    results = sweep(EMACrossover, bars,
                    param_grid={"fast": [8, 12], "slow": [21, 26], "rsi_period": [14]},
                    leverage=5.0)
    print(f"\n--- {sym} ---")
    print(results[["fast", "slow", "sharpe", "max_drawdown", "return"]].head(3))


