# ES/NQ Bear Sweep Research — Master Tracker

**Started**: April 1, 2026  
**Status**: ES champion frozen, temporal OOS not run yet (date-sliced)

---

## Overview

Investigating the same liquidity sweep pattern that works on CL in NY_PRE/AFTER sessions, now on equity index futures (ES and NQ separately).

**Success criteria**: Each instrument passes Phase 1 baseline (n ≥ 20, breakeven win rate), proceeds through Phase 2 (if needed) and Phase 3 (grid search), then OOS validation.

---

## Phase Tracker

| Phase | Task | Status | Start Date | End Date | Notes |
|---|---|---|---|---|---|
| Phase 1 | ES baseline run | ✅ Complete | 2026-04-02 | 2026-04-02 | n=196, marginal fail; isolate sessions |
| Phase 1 | NQ baseline run | ⏳ Pending | — | — | Command: `python strategies/bear_nq_sweep_1h_baseline.py` |
| Phase 1 | Baseline review & decision | ✅ Complete | 2026-04-02 | 2026-04-02 | ES->Phase 2, NQ short leash |
| Phase 2 | ES isolation (if needed) | ✅ Complete | 2026-04-02 | 2026-04-02 | NY_PRE and NY_PRE+LONDON validated |
| Phase 2 | NQ isolation (if needed) | ⏳ Pending | — | — | Test sessions, wick modes, ATR stop |
| Phase 3 | ES grid search | ✅ Complete | 2026-04-02 | 2026-04-02 | Champion selected from NY_PRE+LONDON grid |
| Phase 3 | NQ grid search | ⏳ Pending | — | — | 2-axis grid, motivated parameters only |
| Phase 4 | ES champion freeze | ✅ Complete | 2026-04-02 | 2026-04-02 | `research/results/champions/es_bear_sweep_1h_v1.md` |
| Phase 4 | NQ champion freeze | ⏳ Pending | — | — | Document in `nq_bear_sweep_1h_v1.md` |
| Phase 5 | ES OOS Window 1 | ⏸ Paused | — | — | Blocked: 5m backfill required before true temporal OOS |
| Phase 5 | NQ OOS Window 1 | ⏳ Pending | — | — | Date range: [TBD] |
| Phase 5 | ES OOS Window 2 | ⏸ Paused | — | — | Blocked: 5m backfill required before true temporal OOS |
| Phase 5 | NQ OOS Window 2 | ⏳ Pending | — | — | Date range: [TBD] |
| Phase 5 | ES OOS Window 3 | ⏸ Paused | — | — | Blocked: 5m backfill required before true temporal OOS |
| Phase 5 | NQ OOS Window 3 | ⏳ Pending | — | — | Date range: [TBD] |
| Phase 5 | ES/NQ correlation analysis | ⏳ Pending | — | — | Trade overlap check |
| Phase 4–5 | Portfolio impact sizing | ⏳ Pending | — | — | Estimate combined monthly trade frequency |

---

## Baseline Results Summary

### ES Baseline
```
Status: ✅ COMPLETED — Marginal fail, proceed to Phase 2 isolation
File: strategies/bear_es_sweep_1h_baseline.py
Date: April 2, 2026
```

- **Sweeps total**: 196
- **Converted to trades**: 196 (confirmed full chain)
- **Sample size (n)**: 196 ✅ (≥ 20)
- **Win rate**: 37.8% ❌ (< 44.4% breakeven)
- **Avg R per trade**: ~0.02 (near zero)
- **Sharpe**: ≈ 0 ❌ (breakeven/noisy)
- **Max drawdown**: ~-18R ❌ (heavy risk for tiny return)
- **Total R**: Slightly positive (~+4R) — signal exists but weak
- **Profit factor**: ~1.01 (marginal)

**Session breakdown** (key finding):
- **NY_PRE**: 60 trades, win_rate 45.0%, avg_r +0.065, total_r ≈ +3.9R ✅ **PRIMARY CANDIDATE**
- **LONDON**: 39 trades, win_rate 43.6%, total_r ≈ +2.0R ✅ **SECONDARY CANDIDATE**
- **AFTER**: 10 trades, +3.5R (too thin, exploratory only)
- **ASIA, NY**: Negative total_r (deprioritize)

**Wick quartiles**:
- Q2 and Q4: positive avg_r (Q4 is workhorse)
- Q1 and Q3: negative avg_r (noise)

**Decision**: **INVESTIGATE — Phase 2 isolation** (not grid yet)
- Hypothesis: NY_PRE + wick filtering + tighter stops may unlock the edge
- Isolation sequence: session → wick mode → ATR buffer (in that priority order)

### NQ Baseline
```
Status: ✅ COMPLETED — Clear fail, minimal Phase 2 probes only
File: strategies/bear_nq_sweep_1h_baseline.py
Date: April 2, 2026
```

- **Sweeps total**: 394
- **Converted to trades**: 394
- **Sample size (n)**: 394 ✅ (≥ 20)
- **Win rate**: 16.0% ❌❌ (≪ 44.4% breakeven)
- **Avg R per trade**: ~-0.024 (consistent losses)
- **Sharpe**: < 0 ❌❌ (underwater)
- **Max drawdown**: ~-25R ❌❌ (brutal)
- **Total R**: ≈ -9.4R (structural failure)
- **Profit factor**: < 1.0

**Session breakdown**:
- **ASIA**: 44 trades, win_rate 22.7%, avg_r +0.11, total_r ≈ +4.8R ⚠️ **ONLY BRIGHT SPOT**
- **NY_PRE**: Negative total_r (doesn't work like ES)
- **LONDON, AFTER, NY**: All negative

**Decision**: **STOP after one probe, unless ASIA is slam dunk**
- Run `--allowed-sessions "ASIA"` once to see full stats
- If ASIA stays positive with low drawdown, do one wick probe (Q1_only)
- Otherwise: **Honest failure for NQ on this pattern/timeframe**

---

## Phase 3 Grid Outcome (ES)

### Grid Files
- `results/es_bear_sweep_1h_grid_nypre_v1.csv`
- `results/es_bear_sweep_1h_grid_nypre_london_v1.csv`

### Gate-Passing Leaderboard (Selected)
- **ES-C1 (Champion)**: NY_PRE,LONDON | target_r=1.5 | wick=none | atr=0.5 | n=99 | total_r=10.160185 | pf=1.156250 | sharpe=1.374947 | max_dd=-8.686050
- **ES-C2**: NY_PRE,LONDON | target_r=1.75 | wick=none | atr=0.3 | n=96 | total_r=8.831499 | pf=1.12 | sharpe=1.141592 | max_dd=-8.294777
- **ES-C3**: NY_PRE,LONDON | target_r=1.25 | wick=none | atr=0.5 | n=99 | total_r=5.871442 | pf=1.170213 | sharpe=0.858732 | max_dd=-9.694314
- **ES-C4 (Backup sensitivity variant)**: NY_PRE | target_r=1.5 | wick=none | atr=0.5 | n=60 | total_r=4.624018 | pf=1.064516 | sharpe=1.029200 | max_dd=-9.449771

### Phase 4 Decision
- **Primary champion frozen**: ES-C1
- **Backup documented**: ES-C4 (NY_PRE-only sensitivity variant)
- **Rationale**: ES-C1 has strongest combined Sharpe, total R, and sample size while staying inside drawdown gate.

---

## Phase 5 Audit Note (Important)

- Two earlier "OOS" command runs were executed without date filters and therefore re-ran the full IS period.
- Those runs are reclassified as **IS champion sanity reruns**, not temporal OOS evidence.
- Temporal OOS now requires explicit `--start-date` and `--end-date` in `bear_es_sweep_1h_baseline.py`.

### IS Window Sanity Test (Not OOS)
- Window tested: **2025-03-31 to 2025-05-31** (within tuned IS block).
- Classification: **In-sample window test only** (non-independent), does **not** count toward Phase 5 2-of-3 OOS rule.
- Metrics snapshot: n=20, win_rate=0.600000, total_r=13.629319, profit_factor=3.600000, sharpe=9.555526, max_dd=-2.500000.
- Interpretation: strong local segment behavior; useful intuition for regime sensitivity, but not valid OOS evidence.

### Current Data Coverage Constraint
- MES 5m / MNQ 5m currently span: **2025-03-16 to 2026-03-20**
- MES 1H spans: **2024-02-21 to 2026-03-20**
- Since execution needs 5m data for confirmations, there is currently no truly non-overlapping pre/post IS window available from existing 5m files.
- Action: extend 5m history earlier and/or later, then run true date-sliced OOS windows.

### Backfill Requirements (ES OOS Prerequisite)
- Extend `MES_continuous_5min.parquet` coverage outside IS block (`2025-03-16` to `2026-03-20`).
- Extend `MNQ_continuous_5min.parquet` similarly to keep SMT-aligned intraday context.
- Preferred minimum: add at least 12 months pre-IS (or 12 months post-IS) to enable 3 non-overlapping OOS windows.
- Keep parquet schema/index unchanged to avoid breaking strategy loaders.
- Verify new min/max timestamps before any Phase 5 run.

### Program Decision
- ES remains **IS-validated only** until 5m backfill is complete.
- ES Phase 5 is explicitly paused (not failed).
- Research execution now proceeds to the next strategy in queue while data backfill is prepared.
- Re-open ES Phase 5 immediately after backfill verification.

---

## Key Hypotheses Being Tested

| # | Hypothesis | Expected | Risk | Status |
|---|---|---|---|---|
| 1 | Retail stop clustering is universal across instruments | ES/NQ sweeps reverses like CL | Dark pools + index rebalancing may mask signal | ⏳ Pending baseline |
| 2 | 1H is the right timeframe for ES/NQ sweeps | n ≥ 20 in baseline | May be too coarse; 4H may needed | ⏳ Pending baseline |
| 3 | NY_PRE carries strongest signal | NY_PRE win_rate > overall baseline | Gap fills may dominate; LONDON may stronger | ⏳ Pending Phase 2 |
| 4 | LONDON carries signal on equities (NEW vs CL) | LONDON win_rate > 0 | May not apply; LONDON was excluded from CL | ⏳ Pending Phase 2 |
| 5 | AFTER is weaker on equities than CL | AFTER win_rate < NY_PRE | Post-close equity futures are thinner | ⏳ Pending Phase 2 |
| 6 | 0.5 ATR stop buffer is correct | Grid shows atr_mult_stop ≈ 0.5 | ES/NQ tick size may require 0.3–0.7 | ⏳ Pending Phase 3 |

---

## File Organization

```
strategies/
  bear_es_sweep_1h_baseline.py        ← ES baseline script
  bear_nq_sweep_1h_baseline.py        ← NQ baseline script

research/
  es_nq_bear_sweep_phase1_plan.md     ← Phase 1 execution guide (you are here)
  es_bear_sweep_1h_champion_template.md
  nq_bear_sweep_1h_champion_template.md
  results/
    es_bear_baseline.csv              ← ES baseline report (auto-saved)
    nq_bear_baseline.csv              ← NQ baseline report (auto-saved)
    es_bear_sweep_1h_grid_v1.csv      ← ES grid results (Phase 3)
    nq_bear_sweep_1h_grid_v1.csv      ← NQ grid results (Phase 3)
    champions/
      es_bear_sweep_1h_v1.md          ← ES champion (Phase 4)
      nq_bear_sweep_1h_v1.md          ← NQ champion (Phase 4)
```

---

## Decision Log

### Decision 1: Test All Sessions or Pre-filter?
**Chosen**: Test all sessions (ASIA, LONDON, NY_PRE, NY, AFTER) in baseline.  
**Reason**: Don't pre-exclude LONDON like CL did — equity index futures may show different session patterns.  
**Risk**: Baseline may be noisy with mixed signals. If so, Phase 2 isolation will extract the true signal.

### Decision 2: Use SMT Divergence (ES/NQ)?
**Chosen**: `chain_mode='no_smt_in_chain'` — same as CL champion.  
**Reason**: SMT (ES/NQ divergence) is not part of the core sweep-reverse thesis. Avoids overfitting.  
**Fallback**: Phase 2 isolation can test `chain_mode='baseline_relaxed'` if core signal fails.

### Decision 3: Grid Axes for Phase 3?
**Planned**: 2-axis grid on `(target_r, atr_mult_stop)` or `(target_r, wick_mode)` depending on Phase 2 findings.  
**Reason**: ATR calibration is unknown for ES/NQ (CL-tuned value of 0.5 may not apply). Wick filter may improve signal-to-noise.  
**Constraint**: Max 2 free axes — avoid overfitting on high-liquidity instruments.

### Decision 4: ES OOS Timing
**Chosen**: Pause ES temporal OOS until 5m backfill is available.  
**Reason**: Current intraday coverage overlaps IS block, so no independent OOS windows exist.  
**Execution impact**: Proceed to next strategy now; resume ES at Phase 5 after backfill validation.

---

## Next Steps (Immediate)

1. **Queue and execute 5m backfill** for MES/MNQ outside IS block.
2. **Proceed to next strategy** while backfill runs.
3. **After backfill**, define 3 non-overlapping ES OOS windows and run Phase 5.
4. **Apply ES OOS pass rule** (2/3 windows pass gates) before promotion.
5. **Keep NQ parked** unless a single ASIA-only probe shows strong positive expectancy with controlled drawdown.

---

## Success Metrics

### Baseline Pass Threshold
- n ≥ 20
- win_rate ≥ breakeven_win_rate
- sharpe > 0

### Grid Champion Threshold
- n ≥ 20
- total_r > 0
- profit_factor ≥ 1.10
- max_drawdown ≥ -12R

### OOS Pass Threshold (2 out of 3 windows)
- n ≥ 20
- total_r > 0
- profit_factor ≥ 1.10
- max_drawdown ≥ -12R

### Portfolio Success (both ES and NQ)
- Both instruments pass OOS
- Trade correlation < 70% (insufficient overlap to justify both)
- Combined monthly frequency: 3–5 trades/month across two instruments

---

## Attachments

- `IS_RESEARCH_SOP.md` — Full research standard operating procedure
- `es_nq_bear_sweep_brief.md` — Original strategy brief with hypothesis and rationale






