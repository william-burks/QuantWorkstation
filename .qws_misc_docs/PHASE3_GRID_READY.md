# Phase 3 Grid Search — Ready to Execute

**Date**: April 2, 2026  
**Status**: Grid infrastructure ready  
**Time estimate**: 30–60 min for two grids (NY_PRE, then NY_PRE+LONDON)

---

## Your Phase 2 Findings

✅ **NY_PRE only**: n=60, win_rate 45%, total_r +3.9R, Sharpe 0.93, max_dd -8.4R  
✅ **NY_PRE+LONDON**: n=99, win_rate 44.4%, total_r +5.9R, Sharpe 0.86, max_dd -9.7R  
❌ Wick filtering (exclude_q2, ATR 0.3) degrades the edge  
✅ q3_q4_only keeps signal but with smaller sample  

**Decision**: Run two focused grids on the winning sessions with minimal, motivated axes.

---

## Grid Scope (Per Your Analysis)

### Grid 1: NY_PRE Only
```bash
cd /Users/will/ClaudeProjects/QuantWorkstation

python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --sessions-grid "NY_PRE" \
  --results-csv "results/es_bear_sweep_1h_grid_nypre_v1.csv"
```

**What this tests**:
- 4 target_r values (explore reward scaling)
- 2 wick modes (baseline vs. cleaner)
- 3 ATR stops (tighter, anchor, looser)
- **Total combos**: 4 × 2 × 3 = **24 runs** (~15–20 min)

### Grid 2: NY_PRE + LONDON
```bash
python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --sessions-grid "NY_PRE,LONDON" \
  --results-csv "results/es_bear_sweep_1h_grid_nypre_london_v1.csv"
```

**What this tests**: Same axes but with both sessions (larger sample, more robust).  
**Total combos**: 24 runs (~15–20 min)

---

## Expected Grid Output

For each run, the script will:
1. **Print progress** as each combo completes (target_r, wick_mode, atr_mult_stop, Sharpe)
2. **Save CSV** with all combos ranked by Sharpe
3. **Show top 10** with metrics (n, win_rate, total_r, profit_factor, sharpe, max_dd)

CSV columns:
```
sessions,target_r,wick_mode,atr_mult_stop,n,win_rate,avg_r,total_r,profit_factor,sharpe,max_dd
```

---

## After Grid Completes

### Champion Selection Gate
A configuration qualifies for Phase 4 if it passes **all** of:
- **n ≥ 30** (sufficient sample)
- **win_rate ≥ 45%** (comfortably above breakeven at 44.4%)
- **total_r ≥ +5R** (material edge)
- **profit_factor ≥ 1.15** (clean wins-to-losses ratio)
- **max_dd ≥ -12R** (drawdown control)
- **Sharpe > 0.5** (risk-adjusted edge)

### Next Decision
Once both grids finish:
1. **Review CSV files** and top 10 tables
2. **Identify champion** from grid (likely highest Sharpe that passes all gates)
3. **Compare NY_PRE vs NY_PRE+LONDON** champions (trade sample vs. return)
4. **Pick single champion** for Phase 4 (champion freeze)

If multiple combos qualify, prefer the one with **highest Sharpe** (best risk-adjusted).

---

## Quick Commands (Copy & Paste)

### Run Grid 1 (NY_PRE)
```bash
cd /Users/will/ClaudeProjects/QuantWorkstation
python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --sessions-grid "NY_PRE" \
  --results-csv "results/es_bear_sweep_1h_grid_nypre_v1.csv"
```

### Run Grid 2 (NY_PRE+LONDON)
```bash
python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --sessions-grid "NY_PRE,LONDON" \
  --results-csv "results/es_bear_sweep_1h_grid_nypre_london_v1.csv"
```

### Quick NQ ASIA Probe (Optional)
```bash
python strategies/bear_nq_sweep_1h_baseline.py --allowed-sessions "ASIA" \
  --results-csv "results/nq_phase2_session_asia.csv"
```

---

## Timeline

| Step | Time | Action |
|---|---|---|
| Grid 1 (NY_PRE) | 15–20 min | Run, monitor progress |
| Grid 2 (NY_PRE+LONDON) | 15–20 min | Run, monitor progress |
| NQ ASIA probe (optional) | 5 min | Quick pass/fail on NQ |
| Review CSVs | 10 min | Identify champions, apply gates |
| **Total** | **40–55 min** | Ready for Phase 4 |

---

## Ready?

Start with Grid 1:

```bash
cd /Users/will/ClaudeProjects/QuantWorkstation

python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --sessions-grid "NY_PRE" \
  --results-csv "results/es_bear_sweep_1h_grid_nypre_v1.csv"
```

Grid will auto-print progress and save results CSV. Top 10 will display when complete.

