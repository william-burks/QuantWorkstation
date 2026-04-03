# ES Bear Sweep 1H v1

**Status**: Frozen (Phase 4 complete)
**Freeze Date**: 2026-04-02

---

## Config (Champion)

- Instrument: ES (proxy via MES continuous)
- Direction: BEAR
- Sessions: NY_PRE, LONDON
- Sweep timeframe: 1H
- target_r: 1.5
- atr_mult_stop: 0.5
- wick_mode: none
- chain_mode: no_smt_in_chain
- stop_mode: sweep_atr
- max_hold_bars: 36

---

## IS Metrics (Champion)

- Sample size: 99
- Win rate: 0.373737
- Breakeven win rate: 0.400000
- Avg R/trade: 0.102628
- Total R: 10.160185
- Profit factor: 1.156250
- Sharpe: 1.374947
- Max drawdown (R): -8.686050

Source: `results/es_bear_sweep_1h_grid_nypre_london_v1.csv` (top row)

---

## Why This Works

NY_PRE and LONDON sweeps produce enough failed breakout structure for the 5m confirmation chain to capture downside continuation. The 1.5R target with 0.5 ATR stop keeps payoff asymmetry strong enough to offset a sub-40% win rate.

---

## Known Fragilities

1. Win rate is below 40%, so any reduction in average winner size can quickly break expectancy.
2. Session-dependent edge (NY_PRE/LONDON) can decay under different macro and overnight flow regimes.
3. Execution quality matters: slippage around sweeps can compress the realized R multiple.
4. Over-tightening stops (0.3 in other slices) showed unstable behavior in this dataset.

---

## Backup Config (Sensitivity Variant)

- Sessions: NY_PRE
- target_r: 1.5
- atr_mult_stop: 0.5
- wick_mode: none
- n: 60
- total_r: 4.624018
- profit_factor: 1.064516
- sharpe: 1.029200
- max_dd: -9.449771

Source: `results/es_bear_sweep_1h_grid_nypre_v1.csv` (top row)

---

## OOS Command (Champion)

```zsh
python strategies/bear_es_sweep_1h_baseline.py \
  --target-r 1.5 \
  --atr-mult-stop 0.5 \
  --wick-mode none \
  --allowed-sessions "NY_PRE,LONDON" \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --results-csv results/es_bear_sweep_1h_oos_window1.csv
```

Use three non-overlapping windows with explicit dates. Runs without date flags are IS sanity reruns and do not count as OOS.

---

## OOS Pass/Fail Gates

- Sample size: >= 20
- Total R: > 0
- Profit factor: >= 1.10
- Max drawdown: >= -12R
- Promotion: pass 2 out of 3 OOS windows

---

## Decision Rule (Written Before OOS)

If fewer than 2 of 3 OOS windows pass the gates above, reject this champion and mark strategy failed for this configuration. If 2/3 or more windows pass, promote to live-paper candidate.

---

## Notes

- Grid date: 2026-04-02
- Champion CSV: `results/es_bear_sweep_1h_grid_nypre_london_v1.csv`
- Backup CSV: `results/es_bear_sweep_1h_grid_nypre_v1.csv`
- Freeze rationale: highest Sharpe among gate-passers with strong total R and acceptable drawdown


