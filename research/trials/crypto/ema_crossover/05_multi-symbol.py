# ---
# Experiment 5 — Multi-Symbol
# A strategy that only works on BTC may be curve-fit. Test ETH and SOL.
# Report back: Do the same params work across symbols or does each need its own?

# for sym in ["BTC/USD_1D", "ETH/USD_1D"]:
#     bars = get_store().read_bars("crypto", sym)
#     results = sweep(EMACrossover, bars,
#                     param_grid={"fast": [8, 12], "slow": [21, 26], "rsi_period": [14]},
#                     leverage=5.0)
#     print(f"\n--- {sym} ---")
#     print(results[["fast", "slow", "sharpe", "max_drawdown", "total_return"]].head(3))

