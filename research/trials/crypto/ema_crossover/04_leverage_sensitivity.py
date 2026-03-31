# ---
# Experiment 4 — Leverage Sensitivity
# Find the highest leverage where drawdown stays acceptable.
# Report back: The table of leverage vs drawdown. What's the highest leverage that keeps max_drawdown > -0.50?
# bars = get_store().read_bars("crypto", "BTC/USD_1D")
#
# # Use best params from Experiment 1
# strategy = EMACrossover(fast=8, slow=21)
#
# for lev in [1.0, 2.0, 3.0, 4.0, 5.0]:
#     pf = run(strategy, bars, leverage=lev)
#     equity = pf.value() - (10_000 * lev) + 10_000
#     m = summary(equity)
#     print(
#         f"leverage={lev}x  sharpe={m['sharpe']:.2f}  max_dd={m['max_drawdown']:.2f}  total_return={m['total_return']:.2f}")

