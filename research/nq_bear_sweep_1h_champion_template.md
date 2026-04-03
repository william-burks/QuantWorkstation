# NQ Bear Sweep 1H — Champion Freeze Template

**Status**: [AWAITING PHASE 3 COMPLETION]

Use this template to document the champion after Phase 3 grid search completes.

---

## Config

- **Instrument**: NQ (Nasdaq 100 E-mini futures)
- **Timeframe**: 1H for sweep detection, 5m for confirmation
- **Direction**: Bear (short)
- **Sessions**: [TBD — from Phase 2/3]
- **target_r**: [TBD]
- **min_r_dist**: [TBD]
- **atr_mult_stop**: [TBD — likely 0.3–0.7]
- **wick_mode**: [TBD — likely none, exclude_q2, or q3_q4_only]
- **chain_mode**: no_smt_in_chain (fixed)
- **stop_mode**: sweep_atr (default)
- **max_hold_bars**: 36 (fixed)

---

## IS Metrics

| Metric | Value |
|---|---|
| Sample size (n) | [TBD] |
| Win rate | [TBD] |
| Breakeven win rate | [TBD] |
| Avg R per trade | [TBD] |
| Total R | [TBD] |
| Profit factor | [TBD] |
| Sharpe | [TBD] |
| Max drawdown (R) | [TBD] |
| Monthly consistency | [TBD] |

---

## Why This Works

**Structural Thesis** (1–2 sentences on the mechanical reason for the edge):

[TBD]

---

## Known Fragilities

**Honest assessment** of what could break this signal in out-of-sample trading:

1. **Higher volatility risk**: NQ trades with larger intraday swings than ES. Stops may be too tight, or signal may be noise-driven due to higher vol.

2. **Tech-specific risk**: NQ heavy on mega-cap tech (MSFT, AAPL, NVDA, etc.). Large institutional flows around earnings or macro events may override the liquidity sweep pattern.

3. **Overnight gap sensitivity**: NQ gaps larger overnight on average. NY_PRE sweeps on NQ may be driven by gap fills, not stop clusters.

4. **ATR calibration**: NQ's ATR is higher than ES on absolute terms. If champion uses atr_mult_stop, sensitivity to vol regime is amplified.

5. **ES/NQ correlation**: If both ES and NQ strategies work, their trades may be correlated (both short during same down moves), reducing portfolio diversification benefit.

---

## Backup Config

If champion fails OOS, fallback to this alternative:
- [TBD — typically same as champion but one parameter relaxed, e.g., atr_mult_stop +0.2]

---

## OOS Command

```zsh
python strategies/bear_nq_sweep_1h_baseline.py \
  --target-r [VALUE] \
  --atr-mult-stop [VALUE] \
  --wick-mode [VALUE] \
  --allowed-sessions [VALUE] \
  --results-csv results/nq_bear_sweep_1h_oos_window1.csv
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

If [metric] is [threshold], I will [action].

Example:
- If NQ max drawdown > -15R in any window, I will reject (volatility too high).
- If 2/3 windows pass gates AND ES also passes, I will run both in portfolio.
- If NQ fails but ES passes, I will promote ES only.

[TBD — write this before running OOS]

---

## ES/NQ Correlation Check

After both ES and NQ champions are locked:
- Compare entry times and directions
- If >70% trade overlap → high correlation, run one only
- If <30% trade overlap → low correlation, run both for diversification

[TBD — to be filled after both champions are frozen]

---

## Archive Location

Once frozen, this file goes to: `research/results/champions/nq_bear_sweep_1h_v[N].md`

---

## Notes

- Created: [TBD]
- Grid search date: [TBD]
- Grid results CSV: [TBD]
- Author: [TBD]

