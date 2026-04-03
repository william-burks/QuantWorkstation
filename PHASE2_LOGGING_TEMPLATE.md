# Phase 2 Isolation Results Logging Template

Copy these blocks into `research/es_nq_bear_sweep_tracker.md` as you complete each test.

---

## Phase 2 — ES Isolation Tests (In Progress)

### Test 1A — NY_PRE Only
- **Sessions**: NY_PRE
- **Wick mode**: none
- **ATR mult**: 0.5
- **n**: [pending — check output]
- **win_rate**: [pending]
- **avg_r**: [pending]
- **total_r**: [pending]
- **profit_factor**: [pending]
- **sharpe**: [pending]
- **max_dd**: [pending]

**Expected gate**: win_rate ≥ 43%, total_r ≥ +3.5R  
**Actual result**: [TBD after run]  
**Decision**: [TBD]

---

### Test 1B — NY_PRE + LONDON
- **Sessions**: NY_PRE,LONDON
- **Wick mode**: none
- **ATR mult**: 0.5
- **n**: [pending]
- **win_rate**: [pending]
- **avg_r**: [pending]
- **total_r**: [pending]
- **profit_factor**: [pending]
- **sharpe**: [pending]
- **max_dd**: [pending]

**Expected gate**: win_rate ≥ 44%, total_r ≥ +5.5R  
**Actual result**: [TBD after run]  
**Decision**: [TBD]

---

### Test 2A — NY_PRE + exclude_q2
- **Sessions**: NY_PRE
- **Wick mode**: exclude_q2
- **ATR mult**: 0.5
- **n**: [pending]
- **win_rate**: [pending]
- **avg_r**: [pending]
- **total_r**: [pending]
- **profit_factor**: [pending]
- **sharpe**: [pending]
- **max_dd**: [pending]

**Expected**: Improves win_rate or total_r vs baseline  
**Actual result**: [TBD]  
**Decision**: [TBD]

---

### Test 2B — NY_PRE + q3_q4_only
- **Sessions**: NY_PRE
- **Wick mode**: q3_q4_only
- **ATR mult**: 0.5
- **n**: [pending]
- **win_rate**: [pending]
- **avg_r**: [pending]
- **total_r**: [pending]
- **profit_factor**: [pending]
- **sharpe**: [pending]
- **max_dd**: [pending]

**Expected**: Cleaner signal (Q4 is workhorse)  
**Actual result**: [TBD]  
**Decision**: [TBD]

---

### Test 3A — NY_PRE + [locked_wick] + atr_mult_stop 0.3
- **Sessions**: NY_PRE
- **Wick mode**: [locked from Test 2A or 2B]
- **ATR mult**: 0.3
- **n**: [pending]
- **win_rate**: [pending]
- **avg_r**: [pending]
- **total_r**: [pending]
- **profit_factor**: [pending]
- **sharpe**: [pending]
- **max_dd**: [pending]

**Expected gate**: max_dd improves ≥ 3R  
**Actual result**: [TBD]  
**Decision**: [TBD]

---

## How to Use This Template

1. As each test completes, copy the corresponding section into the tracker
2. Fill in actual values from the printed output (win_rate, total_r, max_dd, etc.)
3. Record your decision (pass gate? continue to next test? adjust parameters?)
4. Move to next test based on decision gate

This prevents context loss and keeps your research log clean.

