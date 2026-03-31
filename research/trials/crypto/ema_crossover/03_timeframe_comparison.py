# ---
# Experiment 3 — Timeframe Comparison
# Intraday bars may produce smaller per-trade losses. Test EMA on 1H and 4H
# Report back: Does intraday reduce max_drawdown vs daily? Which timeframe looks best?
# Run the same EMA sweep from Experiment 1 but swap the bars:

# for tf in ["BTC/USD_1H", "BTC/USD_4H"]:
#     bars = get_store().read_bars("crypto", tf)
#     results = sweep(EMACrossover, bars,
#                     param_grid={"fast": [8, 12, 20], "slow": [21, 26, 50], "rsi_period": [14]},
#                     leverage=5.0, freq="1H")
#     print(f"\n--- {tf} ---")
#     print(results[["fast", "slow", "sharpe", "max_drawdown", "total_return", "n_trades"]].head(5))
