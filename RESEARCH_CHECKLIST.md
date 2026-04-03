# ES/NQ Bear Sweep Research — Phase Checklist

Check off each item as you complete it. This is your daily workflow reference.

---

## 🎯 Phase 1: Baseline Run — TODAY

### ES Baseline
- [ ] Run: `python strategies/bear_es_sweep_1h_baseline.py`
- [ ] Review output: note sample size (n)
- [ ] Check gate: Is n ≥ 20?
- [ ] Record metrics in tracker:
  - [ ] sweeps_total
  - [ ] converted_to_trade
  - [ ] win_rate vs breakeven
  - [ ] avg_r, sharpe, max_dd
- [ ] Review session breakdown: which sessions have most trades?
- [ ] Review wick quartiles: do large wicks (Q3/Q4) outperform small (Q1/Q2)?
- [ ] Decision: Phase 2 isolation or Phase 3 grid?

### NQ Baseline
- [ ] Run: `python strategies/bear_nq_sweep_1h_baseline.py`
- [ ] Review output: note sample size (n)
- [ ] Check gate: Is n ≥ 20?
- [ ] Record metrics in tracker:
  - [ ] sweeps_total
  - [ ] converted_to_trade
  - [ ] win_rate vs breakeven
  - [ ] avg_r, sharpe, max_dd
- [ ] Review session breakdown: which sessions have most trades?
- [ ] Review wick quartiles: do large wicks (Q3/Q4) outperform small (Q1/Q2)?
- [ ] Decision: Phase 2 isolation or Phase 3 grid?

### Phase 1 Decision
- [ ] ES baseline decision recorded in tracker
- [ ] NQ baseline decision recorded in tracker
- [ ] Both proceed to Phase 2/3 OR one/both failed with documented reason

---

## 🔍 Phase 2: Signal Isolation (If Baseline n ≥ 20 but win_rate < breakeven)

### Session Isolation Tests (ES)
Test one session at a time. Record n, win_rate, avg_r for each.

- [ ] NY_PRE only
  - [ ] Result: n=?, win_rate=?, avg_r=?
  - [ ] Decision: improve over baseline?

- [ ] LONDON only
  - [ ] Result: n=?, win_rate=?, avg_r=?
  - [ ] Decision: improve over baseline?

- [ ] AFTER only
  - [ ] Result: n=?, win_rate=?, avg_r=?
  - [ ] Decision: improve over baseline?

- [ ] NY_PRE + AFTER
  - [ ] Result: n=?, win_rate=?, avg_r=?
  - [ ] Decision: improve over baseline?

- [ ] Best session(s) identified: ________________

### Session Isolation Tests (NQ)
Same as ES.

- [ ] NY_PRE only
- [ ] LONDON only
- [ ] AFTER only
- [ ] NY_PRE + AFTER
- [ ] Best session(s) identified: ________________

### Wick Mode Tests (if indicated by baseline wick quartiles)
- [ ] exclude_q2: n=?, win_rate=?, avg_r=?
- [ ] q3_q4_only: n=?, win_rate=?, avg_r=?
- [ ] Best wick mode: ________________

### ATR Stop Buffer Tests (if indicated)
- [ ] atr_mult_stop=0.3: n=?, win_rate=?, avg_r=?
- [ ] atr_mult_stop=0.5: n=?, win_rate=?, avg_r=?
- [ ] atr_mult_stop=0.7: n=?, win_rate=?, avg_r=?
- [ ] Best buffer: ________________

### Phase 2 Summary
- [ ] Isolated signal identified (session / wick mode / buffer)
- [ ] New config shows: win_rate ≥ breakeven, avg_r > baseline
- [ ] Ready for Phase 3 grid search with motivated axes

---

## 📊 Phase 3: Focused Grid Search (If Phase 1 Passes or Phase 2 Isolates Signal)

### ES Grid Setup
- [ ] Motivated axes identified (e.g., target_r, atr_mult_stop)
- [ ] Grid ranges defined:
  - [ ] target_r: ________________
  - [ ] wick_mode: ________________
  - [ ] atr_mult_stop: ________________
  - [ ] sessions: ________________
- [ ] Command written: ________________

### ES Grid Execution
- [ ] Grid runs (may take 10–30 minutes depending on size)
- [ ] Results saved to: `results/es_bear_sweep_1h_grid_v1.csv`
- [ ] Top 10 by Sharpe reviewed
- [ ] Champion identified:
  - [ ] Target R: ________________
  - [ ] Wick mode: ________________
  - [ ] ATR mult stop: ________________
  - [ ] Sessions: ________________
  - [ ] Sample size: ________________
  - [ ] Win rate: ________________
  - [ ] Sharpe: ________________
  - [ ] Profit factor: ________________
  - [ ] Max drawdown: ________________
- [ ] Champion passes gates (n ≥ 20, total_r > 0, profit_factor ≥ 1.10, max_dd ≥ -12R)?
  - [ ] Yes → proceed to Phase 4
  - [ ] No → return to Phase 3 with new axes

### NQ Grid Setup
- [ ] Motivated axes identified
- [ ] Grid ranges defined
- [ ] Command written

### NQ Grid Execution
- [ ] Grid runs
- [ ] Results saved to: `results/nq_bear_sweep_1h_grid_v1.csv`
- [ ] Champion identified (same fields as ES above)
- [ ] Champion passes gates?
  - [ ] Yes → proceed to Phase 4
  - [ ] No → return to Phase 3 with new axes

---

## 🔒 Phase 4: Champion Freeze (After Grid Identifies Winner)

### ES Champion Documentation
- [ ] Fill: `research/es_bear_sweep_1h_champion_template.md`
  - [ ] Config (all parameters explicit)
  - [ ] IS metrics table
  - [ ] Structural thesis (why it works)
  - [ ] Known fragilities (honest risks)
  - [ ] Backup config
  - [ ] OOS command template
  - [ ] OOS pass/fail gates
  - [ ] Decision rule (written before seeing OOS results)
- [ ] Save to: `research/results/champions/es_bear_sweep_1h_v1.md`
- [ ] Lock: no further IS tuning allowed

### NQ Champion Documentation
- [ ] Fill: `research/nq_bear_sweep_1h_champion_template.md`
  - [ ] Config (all parameters explicit)
  - [ ] IS metrics table
  - [ ] Structural thesis
  - [ ] Known fragilities
  - [ ] Backup config
  - [ ] OOS command template
  - [ ] OOS pass/fail gates
  - [ ] Decision rule (written before seeing OOS results)
- [ ] Save to: `research/results/champions/nq_bear_sweep_1h_v1.md`
- [ ] Lock: no further IS tuning allowed

### Confirmation
- [ ] ES champion doc written and saved
- [ ] NQ champion doc written and saved
- [ ] Both decision rules written (before running OOS)
- [ ] Registry updated with new champions

---

## 📈 Phase 5: Out-of-Sample Validation (After Champions Frozen)

### Define OOS Windows
- [ ] OOS Window 1 date range: ________________
- [ ] OOS Window 2 date range: ________________
- [ ] OOS Window 3 date range: ________________
- [ ] Windows do not overlap IS data: ✓
- [ ] Windows are chronologically after IS end: ✓

### ES OOS Window 1
- [ ] Run OOS harness with ES champion config
- [ ] Results saved to: `results/es_bear_sweep_1h_oos_window1.csv`
- [ ] Metrics:
  - [ ] n: ________________
  - [ ] win_rate: ________________
  - [ ] profit_factor: ________________
  - [ ] max_dd: ________________
- [ ] Passes gates? (n ≥ 20, total_r > 0, pf ≥ 1.10, max_dd ≥ -12R)
  - [ ] Yes ✓
  - [ ] No ✗

### ES OOS Window 2
- [ ] Run OOS harness
- [ ] Results saved to: `results/es_bear_sweep_1h_oos_window2.csv`
- [ ] Metrics: n=?, win_rate=?, pf=?, max_dd=?
- [ ] Passes gates?
  - [ ] Yes ✓
  - [ ] No ✗

### ES OOS Window 3
- [ ] Run OOS harness
- [ ] Results saved to: `results/es_bear_sweep_1h_oos_window3.csv`
- [ ] Metrics: n=?, win_rate=?, pf=?, max_dd=?
- [ ] Passes gates?
  - [ ] Yes ✓
  - [ ] No ✗

### ES OOS Decision
- [ ] Windows passed: __/3
- [ ] Promotion rule: 2 out of 3 pass?
  - [ ] Yes → Promote to live paper
  - [ ] No → Reject, document failure

### NQ OOS Windows 1, 2, 3
- [ ] Run OOS harness for all three windows
- [ ] Results saved to:
  - [ ] `results/nq_bear_sweep_1h_oos_window1.csv`
  - [ ] `results/nq_bear_sweep_1h_oos_window2.csv`
  - [ ] `results/nq_bear_sweep_1h_oos_window3.csv`
- [ ] Metrics table:
  - [ ] Window 1: n=?, pf=?, pass?
  - [ ] Window 2: n=?, pf=?, pass?
  - [ ] Window 3: n=?, pf=?, pass?

### NQ OOS Decision
- [ ] Windows passed: __/3
- [ ] Promotion rule: 2 out of 3 pass?
  - [ ] Yes → Promote to live paper
  - [ ] No → Reject, document failure

---

## 📋 Session Close: Before Exiting Research

- [ ] All experiment results saved to `results/`
- [ ] Markdown notes written for this session
- [ ] Champions (if found) frozen and documented
- [ ] OOS harness ready (no manual tweaks needed to run)
- [ ] Registry (`research/results/registry.json`) updated with new strategies
- [ ] Tracker (`research/es_nq_bear_sweep_tracker.md`) updated with final status
- [ ] All fragilities documented honestly
- [ ] Failure notes archived (if applicable)

---

## 📞 Questions During Execution

**Q: My baseline has n < 20. What now?**
A: Below minimum. Either data is too short, or pattern is too rare. Check:
- Are ES/NQ data files complete (years of data)?
- Are sweep detection params correct (swing_n, sweep_lookback)?
- Does a single session (NY_PRE only) have n ≥ 20? If so, isolate to Phase 2.

**Q: Win rate > breakeven but Sharpe is negative. Pass or fail?**
A: Fail Phase 1. Sharpe must also be > 0. (You're winning sometimes but losing bigly other times.)

**Q: My grid found 5 configs all with same high Sharpe. Which is champion?**
A: Highest Sharpe is primary tiebreaker. If tied, pick lowest max drawdown (most stable). Record it and move on.

**Q: ES passed Phase 1, NQ failed. What do I do?**
A: Run ES to OOS only. NQ may work with a different timeframe (4H) or different direction (BULL instead of BEAR) — but that's a new experiment, not continuation of this one.

**Q: OOS Window 1 passed but Window 2 and 3 failed. Reject?**
A: Yes, per rule (2 out of 3 must pass). Don't adjust gates because one window lost money.

**Q: How long until I know if this works?**
A: Phase 1 (baseline) = 1 hour each × 2 scripts = 2 hours. Phase 2 (if needed) = 5–10 tests × 30 min each = 3–5 hours. Phase 3 (grid) = 50–500 runs depending on grid size, ~1–3 hours. Phase 4 (doc) = 30 min. Phase 5 (OOS) = 3–9 hours across three windows. Realistic: **one afternoon to Phase 3 result, one day to OOS decision**.

---

**Printed**: April 1, 2026  
**Status**: Ready for execution  
**Good luck.**

