# ES/NQ Bear Sweep Research — Execution Summary

**Date**: April 1, 2026  
**Status**: Phase 1 scripts ready for execution  
**Next Step**: Run baselines, evaluate results, proceed to Phase 2 (isolation) or Phase 3 (grid)

---

## What Was Built

Two production-ready baseline scripts that test the hypothesis that the liquidity sweep pattern from CL works on equity index futures:

1. **`bear_es_sweep_1h_baseline.py`** — Tests ES (S&P 500) at 1H timeframe
2. **`bear_nq_sweep_1h_baseline.py`** — Tests NQ (Nasdaq 100) at 1H timeframe

Each script:
- Loads 5-minute and 1-hour bars for the target instrument
- Detects 1H swing highs/lows
- Identifies liquidity sweeps (high > swing, close < swing)
- Tests 5m confirmation chain (IFVG, BOS, equal retrace)
- Simulates trades with risk/reward mechanics
- Reports: sample size, win rate, Sharpe, max drawdown, session breakdown, wick quartiles

## Files Created

### Scripts (Ready to Run)
```
strategies/bear_es_sweep_1h_baseline.py
strategies/bear_nq_sweep_1h_baseline.py
```

### Documentation
```
research/
  es_nq_bear_sweep_phase1_plan.md          ← Phase 1 execution guide
  es_nq_bear_sweep_tracker.md              ← Master tracker (fill in as you go)
  es_bear_sweep_1h_champion_template.md    ← Template for Phase 4 (after grid)
  nq_bear_sweep_1h_champion_template.md    ← Template for Phase 4 (after grid)
  run_es_nq_baseline.sh                    ← Quick start shell script
```

### References
```
docs/IS_RESEARCH_SOP.md                    ← Full research standard operating procedure
```

---

## Quick Start

### Run Phase 1 Baselines
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation

# ES baseline
python strategies/bear_es_sweep_1h_baseline.py

# NQ baseline
python strategies/bear_nq_sweep_1h_baseline.py
```

### Or Use Script
```zsh
cd research
chmod +x run_es_nq_baseline.sh
./run_es_nq_baseline.sh
```

---

## What You'll See in Output

Each baseline run prints:

1. **Data loaded**: Rows of MES/MNQ 5m and 1h bars, optional SMT data
2. **Sweep funnel**:
   - Sweeps detected at 1H
   - Filtered by wick mode (default: none, so no filtering)
   - Confirmed by 5m chain (IFVG/BOS)
   - Converted to trades
3. **Key metrics**:
   - Sample size (n)
   - Win rate vs breakeven
   - Avg R, Sharpe, max drawdown
4. **Session breakdown**: Trades per session (NY_PRE, AFTER, LONDON, NY, ASIA)
5. **Wick quartiles**: Which sweep sizes (Q1 small → Q4 large) work best
6. **Monthly P&L**: Consistency across time
7. **Interpretation**: Passes Phase 1 gate or needs Phase 2 isolation

---

## Phase 1 Results (April 2, 2026)

### ES: Marginal Fail → Phase 2 Isolation
- n=196, win_rate 37.8% < 44.4% breakeven, Sharpe ≈ 0
- **BUT**: NY_PRE shows clear signal (60 trades, 45% win_rate, +3.9R total)
- **Action**: Isolate NY_PRE session + wick quality + stop buffer

### NQ: Clear Fail → Minimal Phase 2 Probes Only
- n=394, win_rate 16% << 44.4% breakeven, Sharpe < 0, -9.4R total
- **BUT**: ASIA is anomalously positive (44 trades, 22.7% win_rate, +4.8R)
- **Action**: One quick ASIA-only test; if it fails, park NQ

---

## Decision Gates

### Phase 1 Baseline Gate
✅ **PASS** if: n ≥ 20, win_rate ≥ breakeven, sharpe > 0
→ Proceed to Phase 3 (grid search immediately)

⚠️ **INVESTIGATE** if: n ≥ 20, win_rate < breakeven, but signal visible in sessions/wicks
→ Proceed to Phase 2 (isolation test one variable at a time)

❌ **STOP** if: n < 20 or n ≥ 20 but win_rate << breakeven with no visible signal
→ Document failure, revisit assumptions

---

## Key Hypotheses Being Tested

| # | Hypothesis | Expected | Risk |
|---|---|---|---|
| 1 | Stop clustering is universal | ES/NQ sweeps reverse like CL | Dark pools + index rebalancing hide pattern |
| 2 | 1H is correct timeframe | n ≥ 20, positive expectancy | May need 4H, or pattern too noisy on equities |
| 3 | NY_PRE strongest session | NY_PRE win_rate > AFTER | Gap fills may dominate, LONDON may surprise |
| 4 | LONDON carries signal (new) | LONDON win_rate > 0 | CL excluded LONDON — may not apply to equities |
| 5 | 0.5 ATR stop scales | Grid finds champion near 0.5 | ES/NQ tick size may need 0.3–0.7 |

---

## If Baseline Passes: Phase 3 Grid (Quick Summary)

```zsh
python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,exclude_q2,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --allowed-sessions "NY_PRE,AFTER" \
  --results-csv "results/es_bear_sweep_1h_grid_v1.csv"
```

Grid will test all combinations and return top 10 by Sharpe. Champion is highest Sharpe that passes gates:
- n ≥ 20
- total_r > 0
- profit_factor ≥ 1.10
- max_dd ≥ -12R

---

## If Baseline Fails Gate: Phase 2 Isolation (Quick Summary)

Run one isolation test at a time:

**Session isolation** (fastest signal detection):
```zsh
python strategies/bear_es_sweep_1h_baseline.py --allowed-sessions "NY_PRE"
python strategies/bear_es_sweep_1h_baseline.py --allowed-sessions "LONDON"
python strategies/bear_es_sweep_1h_baseline.py --allowed-sessions "AFTER"
```

If a session shows improvement, lock that session and test other axes in Phase 3 grid.

**Wick mode** (if session breakdown shows Q3/Q4 large wicks work):
```zsh
python strategies/bear_es_sweep_1h_baseline.py --wick-mode "exclude_q2"
python strategies/bear_es_sweep_1h_baseline.py --wick-mode "q3_q4_only"
```

**ATR buffer** (if stop placement matters):
```zsh
python strategies/bear_es_sweep_1h_baseline.py --atr-mult-stop 0.3
python strategies/bear_es_sweep_1h_baseline.py --atr-mult-stop 0.7
```

---

## After Phase 4 (Champion Freeze): Phase 5 OOS

Once champion is locked, run on three OOS date windows (disjoint from IS data):

```zsh
# OOS Window 1
python strategies/bear_es_sweep_1h_baseline.py \
  --target-r [CHAMPION_VALUE] \
  --atr-mult-stop [CHAMPION_VALUE] \
  --allowed-sessions [CHAMPION_VALUE] \
  --results-csv results/es_bear_sweep_1h_oos_window1.csv

# (repeat for windows 2 and 3)
```

**Pass OOS** if **2 out of 3** windows meet minimum gates (same as grid gates).

---

## Data Assumptions

Scripts expect parquet files at:
```
/Users/will/quant-research/data/futures/
  ES_continuous_5min.parquet
  ES_continuous_1H.parquet
  NQ_continuous_5min.parquet
  NQ_continuous_1H.parquet
  MES_continuous_5min.parquet
  MNQ_continuous_5min.parquet
```

If files don't exist, script fails with clear error message. Check file paths before running.

---

## Tracking Progress

**Use this file to track results**: `research/es_nq_bear_sweep_tracker.md`

After each phase, update:
- Phase status (pending → completed)
- Key metrics (n, win_rate, sharpe, etc.)
- Decision (proceed to next phase or stop)
- Notes (which sessions/modes worked, which failed)

---

## SOP Reference

Full research SOP at `docs/IS_RESEARCH_SOP.md` covers:
- Why no phase is skipped
- When to stop vs continue
- How to document failures honestly
- Anti-patterns to avoid

Your baseline scripts implement all Phase 1 requirements:
- ✅ Run with defaults (no tuning yet)
- ✅ Print full funnel report
- ✅ Print session breakdown
- ✅ Print wick quartile table
- ✅ Print monthly P&L
- ✅ Report sample size for gate decision

---

## Success Looks Like

**Best case**: Both ES and NQ baselines pass Phase 1, grid search finds champions for each, both pass OOS in 2/3 windows, trades are uncorrelated, portfolio monthly frequency increases from ~3 trades (CL only) to ~6 trades (CL + ES + NQ).

**Acceptable case**: ES passes, NQ fails or shows weaker signal. Run ES only, add ~2–3 trades/month to portfolio.

**Honest failure case**: One or both instruments show no edge (win_rate << breakeven, no session carries the signal). Document why the hypothesis didn't hold, archive, move on.

---

## You Are Here

You have the tools. Now run the baselines and let the data guide the next phase.

**Next action**: Run both baselines, review the outputs, update the tracker, decide Phase 2 or Phase 3.

