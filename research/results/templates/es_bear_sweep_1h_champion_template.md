# ES Bear Sweep 1H — Champion Freeze

**Status**: Frozen (Phase 4 complete)

Champion selected from Phase 3 grid results.

---

## Config

- **Instrument**: ES (S&P 500 E-mini futures)
- **Timeframe**: 1H for sweep detection, 5m for confirmation
- **Direction**: Bear (short)
- **Sessions**: NY_PRE, LONDON
- **target_r**: 1.5
- **min_r_dist**: 0.10
- **atr_mult_stop**: 0.5
- **wick_mode**: none
- **chain_mode**: no_smt_in_chain (fixed)
- **stop_mode**: sweep_atr (default)
- **max_hold_bars**: 36 (fixed)

---

## IS Metrics

| Metric | Value |
|---|---|
| Sample size (n) | 99 |
| Win rate | 0.373737 |
| Breakeven win rate | 0.400000 |
| Avg R per trade | 0.102628 |
| Total R | 10.160185 |
| Profit factor | 1.156250 |
| Sharpe | 1.374947 |
| Max drawdown (R) | -8.686050 |
| Monthly consistency | Mixed; edge carried by payoff asymmetry |

---

## Why This Works

**Structural Thesis** (1–2 sentences on the mechanical reason for the edge):

NY_PRE and LONDON sweeps produce enough failed breakout structure for the 5m confirmation chain to capture downside continuation. The 1.5R target and 0.5 ATR stop preserve favorable expectancy despite sub-40% win rate.

---

## Known Fragilities

**Honest assessment** of what could break this signal in out-of-sample trading:

1. **Efficiency risk**: ES is the most liquid futures contract in the world. The sweep-and-reverse pattern may exist but be too small to survive transaction costs and slippage.

2. **Pre-market participant mix**: NY_PRE on ES is driven by dark pools and index rebalancing, not retail stop clustering like CL. If the signal lives in NY_PRE, it may not hold OOS.

3. **ATR calibration**: 0.5 ATR is currently robust; 0.7 degraded performance sharply and tighter stops were unstable in filtered slices.

4. **Session decay**: If sessions carry different weights (LONDON strong, AFTER weak), a shift in trading hours could dilute the signal.

5. **SMT divergence**: If champion includes SMT filter, ES/NQ divergence may be a data artifact or ephemeral pattern.

---

## Backup Config

If champion fails OOS, fallback to this alternative:
- Sessions: NY_PRE
- target_r: 1.5
- atr_mult_stop: 0.5
- wick_mode: none
- Metrics: n=60, total_r=4.624018, profit_factor=1.064516, sharpe=1.029200, max_dd=-9.449771

---

## OOS Command

```zsh
python strategies/bear_es_sweep_1h_baseline.py \
  --target-r 1.5 \
  --atr-mult-stop 0.5 \
  --wick-mode none \
  --allowed-sessions "NY_PRE,LONDON" \
  --results-csv results/es_bear_sweep_1h_oos_window1.csv
```

Run on three separate date windows:
1. **OOS Window 1**: [TBD — date range after IS end]
2. **OOS Window 2**: [TBD — next date range]
3. **OOS Window 3**: [TBD — next date range]

---

## OOS Pass/Fail Gates

Champion passes OOS if **2 out of 3** windows meet:
- Sample size: ≥ 20
- Total R: > 0
- Profit factor: ≥ 1.10
- Max drawdown: ≥ -12R

---

## Decision Rule (Write Before Seeing OOS Numbers)

If fewer than 2 of 3 OOS windows pass the gates, I will reject this champion and mark it failed for this configuration. If 2/3 or more windows pass, I will promote it to live-paper candidate.

---

## Archive Location

Once frozen, this file goes to: `research/results/champions/es_bear_sweep_1h_v[N].md`

---

## Notes

- Created: 2026-04-01
- Grid search date: 2026-04-02
- Grid results CSV: results/es_bear_sweep_1h_grid_nypre_london_v1.csv
- Backup CSV: results/es_bear_sweep_1h_grid_nypre_v1.csv
- Champion file: research/results/champions/es_bear_sweep_1h_v1.md


