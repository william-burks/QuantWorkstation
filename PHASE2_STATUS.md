# ✅ CLI Arguments Fixed — Phase 2 Tests Running

**Date**: April 2, 2026  
**Status**: Phase 2 tests in progress (Tests 1A–3A)

---

## What Was Fixed

### Problem
The baseline scripts only had `--results-csv` argument support. They were missing:
- `--allowed-sessions` (needed for session isolation)
- `--wick-mode` (needed for wick filtering)
- `--atr-mult-stop` (needed for stop buffer testing)
- All other parameter overrides

### Solution
Added full CLI argument parser to both scripts:
- ✅ `strategies/bear_es_sweep_1h_baseline.py` — Now supports all Phase 2 parameters
- ✅ `strategies/bear_nq_sweep_1h_baseline.py` — Now supports all Phase 2 parameters

### Supported Arguments (All Optional)
```
--allowed-sessions    Comma-separated sessions (ASIA,LONDON,NY_PRE,NY,AFTER)
--wick-mode          Wick filter: none, exclude_q2, q3_q4_only
--atr-mult-stop      Stop buffer multiplier (default 0.5)
--target-r           Target R value (default 1.25)
--min-r-dist         Minimum R distance (default 0.10)
--stop-mode          Stop mode: sweep_atr or 5m_lower_high
--chain-mode         Confirmation chain mode
--max-hold-bars      Maximum hold bars
[+ 6 more parameters]
```

---

## Test Execution Status

Running all 5 ES Phase 2 isolation tests:

| Test | Description | Status | Expected | Notes |
|---|---|---|---|---|
| 1A | NY_PRE only | ✅ Complete | n~60, win_rate 45%, total_r +3.9R | Session isolation axis 1 |
| 1B | NY_PRE + LONDON | ✅ Complete | n~99, win_rate 44%, total_r +5.9R | Session isolation axis 2 |
| 2A | NY_PRE + exclude_q2 | ✅ Complete | Should improve over baseline | Wick filtering axis 1 |
| 2B | NY_PRE + q3_q4_only | ✅ Complete | Cleaner signal (Q4 workhorse) | Wick filtering axis 2 |
| 3A | NY_PRE + exclude_q2 + 0.3 ATR | 🔄 Running | Tighter stop, lower max_dd | Stop buffer axis 1 |
| 3B | NY_PRE + exclude_q2 + 0.7 ATR | ⏳ Pending | Looser stop, higher total_r | Stop buffer axis 2 (optional) |

**Elapsed time**: ~30 min (started ~7:40 AM)  
**Estimated completion**: 5–10 min more

---

## Test Output Format

Each test prints:
```
loaded_rows: mes5=XXXX mes1h=YYYY mnq5=ZZZZ
Total qualifying sweeps: N

[Sweeps by Session breakdown]

--- Confirmation Chain Funnel ---
sweeps_total: N
sweeps_after_wick_filter: N
skipped_chain: N
skipped_r_dist: N
converted_to_trade: N

sample_size: N
win_rate: X.XXXXXX
avg_win_r: X.XXXXXX
avg_loss_r: X.XXXXXX
total_r: X.XXXXXX
avg_r_per_trade: X.XXXXXX
profit_factor: X.XXXXXX
sharpe: X.XXXXXX
max_drawdown_r: X.XXXXXX
[...]

--- Session Breakdown ---
[table by session]

--- Wick Size Quartiles ---
[table by quartile]

--- Monthly P&L ---
[monthly breakdown]

Interpretation: [Verdict]
```

Results also auto-saved to `results/es_phase2_*.csv` for import/analysis.

---

## Next Steps (When Tests Complete)

1. **Review output** for each test (already printed to console)
2. **Log results** in `research/es_nq_bear_sweep_tracker.md` using `PHASE2_LOGGING_TEMPLATE.md`
3. **Apply decision gates**:
   - Test 1A: If win_rate ≥ 43% & total_r ≥ +3.5R → continue to 1B
   - Test 1B: If win_rate ≥ 44% & total_r ≥ +5.5R → lock session, go to Axis 2
   - Test 2A/2B: If improvement → lock wick, go to Axis 3
   - Test 3A: If max_dd improves ≥ 3R → lock 0.3 ATR
4. **Decide Phase 3**: If final combo meets all gates (n ≥ 30, win_rate ≥ 45%, total_r ≥ +5R, pf ≥ 1.15, max_dd ≥ -12R) → promote to Phase 3 grid. Otherwise → archive.

---

## Files Ready

- ✅ `strategies/bear_es_sweep_1h_baseline.py` — Full CLI support
- ✅ `strategies/bear_nq_sweep_1h_baseline.py` — Full CLI support
- ✅ `research/run_es_phase2.sh` — Automated test runner
- ✅ `research/ES_PHASE2_ISOLATION_PLAN.md` — Detailed isolation specs
- ✅ `PHASE2_LOGGING_TEMPLATE.md` — Copy/paste logging template
- ✅ `research/es_nq_bear_sweep_tracker.md` — Master results log

---

## Quick Reference: How to Run Tests

Once current tests finish, you can run individual tests:

```bash
cd /Users/will/ClaudeProjects/QuantWorkstation/research

# Run specific test
./run_es_phase2.sh 1a      # NY_PRE only
./run_es_phase2.sh 1b      # NY_PRE + LONDON
./run_es_phase2.sh 2a      # NY_PRE + exclude_q2
./run_es_phase2.sh 2b      # NY_PRE + q3_q4_only
./run_es_phase2.sh 3a      # NY_PRE + exclude_q2 + 0.3 ATR
./run_es_phase2.sh nq      # NQ ASIA quick probe

# Or run all
./run_es_phase2.sh all     # Run 1a through 3a
```

---

**Status**: Tests in progress. Check back in 5–10 min for full results.

