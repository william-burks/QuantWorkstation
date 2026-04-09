# CL Bear Sweep 1H No Pivot

**Status**: Frozen (Phase 4 complete)
**Freeze Date**: 2026-04-08

---

## Config (Champion)

- Instrument: CL
- Direction: BEAR
- Sessions: NY_PRE, LONDON
- Sweep timeframe: 1H
- target_r: 1.25
- atr_mult_stop: 0.5
- wick_mode: exclude_q2
- chain_mode: no_smt_in_chain
- stop_mode: sweep_atr
- max_hold_bars: 24

---

## IS Metrics (Champion)

- Sample size: 45
- Win rate: 0.600000
- Breakeven win rate: 0.444444
- Avg R/trade: 0.182000
- Total R: 8.19
- Profit factor: 3.10
- Sharpe: 2.60
- Max drawdown (R): -0.06

Source: `research/results/futures/liquidity_sweep/runs/20260408-200715/baseline_results.csv` (top row)

---

## Why This Works

CL 1H bear sweeps in NY_PRE and LONDON sessions consistently reject failed breakouts with strong continuation. The exclude_q2 wick filter removes ambiguous wicks that reduce expectancy.

---

## Known Fragilities

1. Edge is session-dependent — degradation likely if NY_PRE open character changes under different volatility regimes.
2. CL liquidity structure differs from equity index sweeps; inventory cycle shifts can compress payoff ratio.
3. Sample is concentrated in a single directional bias; no evidence of edge in bull direction.

---

## OOS Command (Champion)

```zsh
python strategies/bear_cl_sweep_1h_baseline.py \
  --target-r 1.25 \
  --atr-mult-stop 0.5 \
  --wick-mode exclude_q2 \
  --allowed-sessions "NY_PRE,LONDON" \
  --start-date 2025-01-01 \
  --end-date 2025-06-30 \
  --results-csv research/results/futures/liquidity_sweep/oos/cl_bear_sweep_1h_oos_window1.csv
```
