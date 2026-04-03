# Phase 2 Execution — Quick Start

**Date**: April 2, 2026  
**Status**: Baseline complete, Phase 2 isolation ready  
**Time estimate**: 25–30 min for full ES isolation + NQ quick probe

---

## Your Options

### Option A: ES-Focused Deep Dive (Recommended)
Focus all cycles on ES isolation. Highest ROI given ES has detectable signal.

```bash
cd research
chmod +x run_es_phase2.sh
./run_es_phase2.sh all
```

This runs:
1. NY_PRE only
2. NY_PRE + LONDON
3. NY_PRE + exclude Q2
4. NY_PRE + Q3/Q4 only
5. NY_PRE + exclude Q2 + 0.3 ATR

Each test takes ~5 min. **25 min total**, results in `results/es_phase2_*.csv`.

Then: **Decide** if any combo beats baseline (pass gate). If yes → Phase 3 grid. If no → archive ES.

### Option B: Quick NQ Probe Then ES Deep Dive
Test NQ ASIA anomaly (5 min), then commit to ES isolation if NQ fails.

```bash
# NQ quick test
./run_es_phase2.sh nq

# If NQ ASIA is negative, proceed to ES:
./run_es_phase2.sh all
```

### Option C: Manual, Strategic (Most Control)
Run tests one at a time, **log results in tracker after each**, and make decisions in real-time.

```bash
# Test 1A
./run_es_phase2.sh 1a
# → Review output, log in tracker
# → If pass gate (win_rate ≥ 43%, total_r ≥ +3.5R), proceed to 1B

# Test 1B
./run_es_phase2.sh 1b
# → Log in tracker
# → If NY_PRE+LONDON holds, lock session; if it worsens, revert to NY_PRE

# Test 2A (wick)
./run_es_phase2.sh 2a
# → Log. If exclude_q2 helps, continue. If not, try 2B.

# etc.
```

---

## What to Log After Each Test

**Template** (paste into `research/es_nq_bear_sweep_tracker.md`):

```markdown
### Phase 2 — ES Isolation Tests

**Test 1A — NY_PRE Only**
- Sessions: NY_PRE
- Wick mode: none
- ATR mult: 0.5
- **n**: [count from output]
- **win_rate**: [%]
- **avg_r**: [value]
- **total_r**: [value]
- **profit_factor**: [value]
- **sharpe**: [value]
- **max_dd**: [value]
- **Gate**: win_rate ≥ 43%, total_r ≥ +3.5R?
  - YES → Proceed to Test 1B
  - NO → Try wick axis (Test 2A)
```

Copy this template and fill in actual numbers from the printed output.

---

## Decision Flow (Quick Reference)

```
Test 1A (NY_PRE only)
    ↓
[win_rate ≥ 43% & total_r ≥ +3.5R?]
    ├─ YES → Test 1B (add LONDON)
    ├─ NO → Test 2A (try wick filter)
    └─ COLLAPSE (total_r < 0) → STOP ES

Test 1B (NY_PRE + LONDON)
    ↓
[win_rate ≥ 44% & total_r ≥ +5.5R?]
    ├─ YES → Lock NY_PRE+LONDON, go to Axis 2
    ├─ WORSE → Revert to NY_PRE, go to Axis 2
    └─ COLLAPSE → STOP ES

Test 2A (exclude Q2) or 2B (Q3/Q4 only)
    ↓
[win_rate improves & total_r improves?]
    ├─ YES → Lock wick mode, go to Axis 3
    ├─ NO → Keep default wick mode, skip Axis 3
    └─ WORSE → Try other wick mode

Test 3A (0.3 ATR) or 3B (0.7 ATR)
    ↓
[max_dd improves ≥ 3R?]
    ├─ YES → Lock ATR mult
    └─ NO → Keep 0.5

Final Combo:
    ↓
[n ≥ 30 & win_rate ≥ 45% & total_r ≥ +5R & pf ≥ 1.15 & max_dd ≥ -12R?]
    ├─ YES → Promote to Phase 3 grid
    └─ NO → Archive ES as "marginal fail"
```

---

## NQ Decision (Single Quick Test)

```bash
./run_es_phase2.sh nq
```

Output will show ASIA-only stats. If:
- **total_r ≥ +4R & win_rate ≥ 20% & max_dd < -15R** → Consider one wick test (`q1_only`)
- **Otherwise** → Log result and archive NQ ("honest failure on this pattern/timeframe")

---

## After Phase 2

### If ES Isolation Succeeds
→ **Phase 3 Grid**: Lock the session+wick+ATR combo and run a 2-axis grid on target_r and one other parameter (e.g., stop_mode). Estimate 1–3 hours for grid.

### If ES Isolation Fails
→ **Archive**: Document why (e.g., "NY_PRE signal collapsed in isolation" or "wick filtering made things worse"). Move focus to CL and other strategies.

### NQ Result
→ **If ASIA holds**: One wick probe, then archive. **If ASIA fails**: Immediate archive.

---

## Files to Update

After each test, update:
- `research/es_nq_bear_sweep_tracker.md` (add Phase 2 section with test results)
- `research/ES_PHASE2_ISOLATION_PLAN.md` (mark tests completed, note decisions)

---

## Ready?

**Pick your approach (A, B, or C) and start:**

```bash
cd /Users/will/ClaudeProjects/QuantWorkstation/research
chmod +x run_es_phase2.sh

# Option A: Go all-in on ES
./run_es_phase2.sh all

# Option B: NQ first, then ES
./run_es_phase2.sh nq && ./run_es_phase2.sh all

# Option C: One test at a time (most control)
./run_es_phase2.sh 1a  # Review, log, decide
./run_es_phase2.sh 1b  # etc.
```

**Estimate 30 min to full results, or 5 min for NQ quick probe + call on ES.**

What's your time window?

