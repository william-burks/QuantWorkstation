# ES/NQ Phase 2 Isolation — Action Plan

**Date**: April 2, 2026  
**Status**: Ready to execute  
**Priority**: ES-focused (NQ minimal probe only)

---

## Overview

**ES**: Marginal fail (Sharpe ≈ 0, win_rate 37.8% < breakeven) but **NY_PRE shows a clear signal** (45% win rate, +3.9R). Phase 2 isolation will test whether filtering to NY_PRE + wick quality + tighter stops recovers a tradeable edge.

**NQ**: Structural fail (16% win rate, -9.4R total) except **ASIA is anomalously positive** (+4.8R). Phase 2 is a single quick probe: if ASIA holds, one wick test; otherwise, stop.

---

## ES Phase 2: Three-Axis Isolation (Sequential)

### Axis 1: Session Filter (Highest Leverage)

Run these in order. Stop early if direction is wrong.

#### Test 1A: NY_PRE Only
```bash
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE" \
  --results-csv "results/es_phase2_session_nypre.csv"
```

**Expected**: ~60 trades, win_rate ≥ 45%, total_r ≈ +4R  
**Log result**: n, win_rate, avg_r, total_r, profit_factor, sharpe, max_dd

**Decision gate**:
- If win_rate ≥ 43% AND total_r ≥ +3.5R → **Proceed to Test 1B**
- If win_rate < 40% OR total_r < +3R → **Wick axis (Test 2A) before further session combos**
- If total_r < 0 → Stop ES immediately (signal collapsed in isolation)

#### Test 1B: NY_PRE + LONDON (if 1A passes)
```bash
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE,LONDON" \
  --results-csv "results/es_phase2_session_nypre_london.csv"
```

**Expected**: ~99 trades (60 + 39), win_rate ≥ 44%, total_r ≈ +5.9R  
**Log result**: Same metrics as above

**Decision gate**:
- If win_rate ≥ 44% AND total_r ≥ +5.5R → **Lock this session combo, proceed to Axis 2 (wick)**
- If win_rate drops below 44% → **Revert to NY_PRE only for Axis 2**
- If total_r deteriorates → Investigate whether LONDON is noise; may drop LONDON

### Axis 2: Wick Quality (Only After Session Lock)

Once you've locked a session combo (likely NY_PRE or NY_PRE+LONDON), test wick filters **inside that session**.

#### Test 2A: Exclude Q2 Wicks (within locked session)
```bash
# If NY_PRE is locked:
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE" \
  --wick-mode "exclude_q2" \
  --results-csv "results/es_phase2_nypre_exclude_q2.csv"
```

**Expected**: Fewer trades (~45–50), but higher avg_r and win_rate (Q2 is noise)

**Decision gate**:
- If win_rate improves ≥ 2% AND total_r improves → **This is good; keep this combo**
- If win_rate stays flat or drops → **Q2 exclusion doesn't help; move to Test 2B**

#### Test 2B: Keep Only Q3+Q4 (within locked session)
```bash
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE" \
  --wick-mode "q3_q4_only" \
  --results-csv "results/es_phase2_nypre_q3q4_only.csv"
```

**Expected**: ~30–35 trades (Q1+Q2 removed), but much cleaner (Q4 is the workhorse, Q3 is acceptable noise filter)

**Decision gate**:
- If n ≥ 25 AND win_rate ≥ 48% AND total_r ≥ +2.5R → **Strong candidate; lock this**
- If n < 20 OR win_rate < 45% → **Too thin; use "exclude_q2" instead if that was better**

**Choose the best outcome from 2A or 2B as your locked wick mode.**

### Axis 3: ATR Stop Buffer (Only If Above Passes)

Once you have a locked session + wick combo that beats baseline, test stop calibration.

#### Test 3A: Tighter Stop (0.3 ATR)
```bash
# Assuming NY_PRE + exclude_q2 or q3_q4_only is locked:
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE" \
  --wick-mode "exclude_q2" \
  --atr-mult-stop 0.3 \
  --results-csv "results/es_phase2_nypre_exclude_q2_atr03.csv"
```

**Expected**: ~same number of trades, but lower max_dd (tighter stop), possibly lower total_r (stop hit early more often)

**Decision gate**:
- If max_dd improves by ≥ 3R AND total_r doesn't drop >0.5R → **Strong improvement, use 0.3**
- If max_dd doesn't improve or total_r drops significantly → **Keep default 0.5**

#### Test 3B: Looser Stop (0.7 ATR) (optional, only if 3A doesn't help)
```bash
python strategies/bear_es_sweep_1h_baseline.py \
  --allowed-sessions "NY_PRE" \
  --wick-mode "exclude_q2" \
  --atr-mult-stop 0.7 \
  --results-csv "results/es_phase2_nypre_exclude_q2_atr07.csv"
```

**Expected**: Larger max_dd but potentially higher total_r (trades run further)

**Decision gate**:
- If total_r improves ≥ 0.5R AND max_dd worsens ≤ 4R → **Consider 0.7**
- Otherwise keep 0.5

---

## ES Phase 2 Exit Criteria

### Promote to Phase 3 Grid if:
- **Session + wick + ATR combo achieves**:
  - n ≥ 30
  - win_rate ≥ 45%
  - total_r ≥ +5R
  - profit_factor ≥ 1.15
  - max_dd ≥ -12R (not worse than baseline)
  - Sharpe > 0.5

**Then run a full 2-axis grid** on that session+wick combo with target_r and one other axis (e.g., stop_mode).

### Stop ES Immediately if:
- After 3–4 well-chosen isolation runs, total_r remains near zero or negative
- Session collapse (e.g., NY_PRE collapses in isolation)
- Max drawdown worsens >25R without compensating returns

---

## NQ Phase 2: Minimal Probe

### Single Test: ASIA Only
```bash
python strategies/bear_nq_sweep_1h_baseline.py \
  --allowed-sessions "ASIA" \
  --results-csv "results/nq_phase2_asia_only.csv"
```

**Expected**: ~44 trades, win_rate 22.7%, avg_r +0.11, total_r ≈ +4.8R

**Decision gate**:
- If **total_r ≥ +4R AND win_rate ≥ 20% AND max_dd < -15R** → **ASIA is a genuine signal; do one wick test**
  - Run: `--allowed-sessions "ASIA" --wick-mode "q1_only"` (Q1 small wicks performed well in ASIA)
  - If wick improves metrics, note for future NQ research but **do not commit further cycles**
- If **total_r < +3R OR win_rate < 20% OR max_dd < -15R** → **Honest failure; park NQ**

---

## Execution Sequence (Recommended)

**Today (prioritize ES)**:
1. Run Test 1A (NY_PRE) — ~5 min
2. If pass gate, run Test 1B (NY_PRE+LONDON) — ~5 min
3. Lock session, run Test 2A or 2B (wick) — ~5 min
4. If wick helps, run Test 3A (tighter stop) — ~5 min

**Quick NQ probe**:
5. Run NQ ASIA test in parallel or after ES, ~5 min

**Total elapsed**: ~25–30 min for ES full 3-axis isolation, plus 5 min NQ quick check.

**Log every run** into tracker before moving to next test (3 seconds per run, prevents context loss).

---

## Logging Template

For each run, record in `research/es_nq_bear_sweep_tracker.md`:

```
**Test [ID] — [Description]**
- Sessions: [value]
- Wick mode: [value]
- ATR mult: [value]
- **n**: [count]
- **win_rate**: [%]
- **avg_r**: [value]
- **total_r**: [value]
- **profit_factor**: [value]
- **sharpe**: [value]
- **max_dd**: [value]
- **Verdict**: [pass/fail gate, next test]
```

---

## What Success Looks Like

ES Phase 2 success: **Find a session+wick+stop combo where win_rate ≥ 45%, total_r ≥ +5R, and max_dd ≤ -12R.**

NQ Phase 2 success: **ASIA-only NQ stays positive with low drawdown; otherwise archived as honest failure.**

---

## If You Get Stuck

- **ES total_r collapses in isolation**: The session-level signal may be a fluke or depend on interactions with other sessions. Try broader sessions (add AFTER or NY back) to see if it recovers.
- **Wick mode doesn't help ES**: Skip straight to ATR stop testing; wick may be a red herring.
- **NQ ASIA fails**: Don't waste more time; recommend archiving NQ for this pattern/timeframe and focusing on ES + CL going forward.

Ready to execute. What's your time availability today—full ES isolation loop, or quick NQ probe first then deep ES tomorrow?

