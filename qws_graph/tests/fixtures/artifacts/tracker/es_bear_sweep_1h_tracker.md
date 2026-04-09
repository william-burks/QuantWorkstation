# ES Bear Sweep 1H — Research Tracker

## Status
Active — Phase 3 complete, grid sweep done, champion pending

## Hypothesis
Failed breakout sweeps in NY_PRE and LONDON sessions produce directional continuation with consistent payoff asymmetry at 1H timeframe.

## What We Know

- Grid confirms edge exists at target_r 1.5, atr_mult_stop 0.5, NY_PRE + LONDON sessions
- Sharpe 1.37, profit_factor 1.16, win_rate 0.37 across 99 trades
- Drawdown acceptable at -8.69R over the IS period
- Q1-only wick filter tested; degraded results (sharpe dropped to 0.96)
- Single-session (NY_PRE only) shows weaker edge; session pairing is load-bearing

## Open Questions

1. Does the edge hold in CL (crude oil) under the same sweep logic?
2. Can we tighten the stop (0.3 ATR) without sacrificing too many winners?
3. Is the 1.5R target optimal or does 1.25R show better win-rate-weighted expectancy?

## Next Steps

- Run OOS window 1 (2024-01-01 to 2024-06-30) with frozen params
- If OOS Sharpe ≥ 1.0, proceed to champion promotion
- Draft champion_md after OOS confirms