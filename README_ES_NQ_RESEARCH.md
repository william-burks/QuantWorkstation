# ES/NQ Bear Sweep Research — Complete Setup ✓

**Date**: April 1, 2026  
**Status**: Ready to execute  
**Time to baseline results**: ~2 hours

---

## What You Have

Two production-ready baseline scripts + full research infrastructure following the IS Research SOP (standard operating procedure).

## Start Here

### Quick Start (2 minutes)
Read: `ES_NQ_RESEARCH_SUMMARY.md` (in this directory)

### Run Phase 1 (2 hours)
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
python strategies/bear_es_sweep_1h_baseline.py
python strategies/bear_nq_sweep_1h_baseline.py
```

### Track Progress
Update: `research/es_nq_bear_sweep_tracker.md` after each phase

### Daily Workflow
Use: `RESEARCH_CHECKLIST.md` to track which items are done

---

## Full File Map

### Scripts (Ready to Run)
```
strategies/bear_es_sweep_1h_baseline.py          Production baseline, can also run grid
strategies/bear_nq_sweep_1h_baseline.py          Production baseline, can also run grid
```

### Executive Docs
```
ES_NQ_RESEARCH_SUMMARY.md                        START HERE — Overview + quick reference
RESEARCH_CHECKLIST.md                            Daily workflow checklist for all 5 phases
```

### Research Documentation
```
research/
  es_nq_bear_sweep_phase1_plan.md               Phase 1 detailed execution guide
  es_nq_bear_sweep_tracker.md                   Master results tracker (fill as you go)
  es_bear_sweep_1h_champion_template.md         Template for Phase 4 (champion freeze)
  nq_bear_sweep_1h_champion_template.md         Template for Phase 4 (champion freeze)
  run_es_nq_baseline.sh                         Shell script to auto-run baselines
```

### Results (Auto-generated After Runs)
```
research/results/
  es_bear_baseline.csv                          ES Phase 1 output
  nq_bear_baseline.csv                          NQ Phase 1 output
  es_bear_sweep_1h_grid_v1.csv                  ES Phase 3 grid (after grid run)
  nq_bear_sweep_1h_grid_v1.csv                  NQ Phase 3 grid (after grid run)
  champions/
    es_bear_sweep_1h_v1.md                      ES champion doc (Phase 4)
    nq_bear_sweep_1h_v1.md                      NQ champion doc (Phase 4)
    registry.json                               Strategy registry (updated per phase)
```

### Reference (Read for Context)
```
docs/IS_RESEARCH_SOP.md                         Full research SOP (5 phases, decision gates, anti-patterns)
```

---

## Key Decisions Made For You

| Decision | Choice | Reason |
|---|---|---|
| **Test all sessions?** | Yes (ASIA, LONDON, NY_PRE, NY, AFTER) | Don't pre-exclude LONDON like CL did — equity indices may behave differently |
| **Use SMT divergence?** | No (chain_mode=no_smt_in_chain) | Keep it simple, avoid overfitting; can test later |
| **Grid axes (Phase 3)?** | target_r × atr_mult_stop (motivated by data) | Not exhaustive search; max 2 free axes to avoid overfitting |
| **OOS pass rule?** | 2 out of 3 windows must pass | Realistic for edge case where one window is unlucky |
| **Data paths?** | `/Users/will/quant-research/data/futures/` | Matches your existing pipeline |

---

## Success Criteria

### Phase 1 Baseline (You are here)
- ✅ **PASS**: n ≥ 20, win_rate ≥ breakeven_win_rate, sharpe > 0 → Go to Phase 3 (grid)
- ⚠️ **INVESTIGATE**: n ≥ 20, win_rate < breakeven, but visible signal in sessions/wicks → Go to Phase 2 (isolation)
- ❌ **STOP**: n < 20 or no visible signal → Document failure, revisit assumptions

### Phase 3 Grid (if Phase 1 passes)
- ✅ At least one config passes all gates (n ≥ 20, total_r > 0, profit_factor ≥ 1.10, max_dd ≥ -12R) → Go to Phase 4 (freeze)
- ❌ No config passes gates → Go back to Phase 3 with new axes or stop

### Phase 5 OOS (after Phase 4 champion frozen)
- ✅ **PROMOTE**: 2 out of 3 OOS windows pass gates → Go to live paper
- ❌ **REJECT**: Fewer than 2 windows pass gates → Document failure, archive

---

## Honest Risk Assessment

**Most likely failure mode**: ES is too efficient. The sweep-and-reverse pattern exists but is too small to trade profitably after slippage/fees.

**Second most likely**: NY_PRE on equities is dominated by gap fills and index rebalancing, not the retail stop clustering that works on CL.

**Best case**: London open (which CL excluded) carries the signal on equity index futures, giving you a new session-specific edge.

---

## Next Steps (In Order)

1. **Read** `ES_NQ_RESEARCH_SUMMARY.md` (5 min)
2. **Run** ES and NQ baselines (2 hours)
3. **Review** output, check Phase 1 gate
4. **Update** tracker with results
5. **Decide**: Phase 2 (isolation) or Phase 3 (grid)?
6. **Execute** Phase 2 or Phase 3 based on baseline decision
7. **Proceed** through Phases 4–5 per checklist

---

## Questions?

Refer to:
- General research process → `docs/IS_RESEARCH_SOP.md`
- This specific study → `research/es_nq_bear_sweep_phase1_plan.md`
- Execution questions → `RESEARCH_CHECKLIST.md` (Q&A section)

---

## Metrics to Expect (Rough Ranges)

Based on CL bear sweep (Sharpe 4.8, win_rate 31%, n=32):

- **ES baseline**: Expect lower (ES is more efficient than CL)
  - Realistic: Sharpe 1.5–2.5, win_rate 30–50%, n 20–50
- **NQ baseline**: Expect more volatile
  - Realistic: Sharpe 0.5–2.0, win_rate 25–45%, n 15–40

If either shows n < 20 or sharpe < 0, Phase 2 isolation will find the session(s) that work.

---

**Created**: April 1, 2026  
**Ready**: Yes  
**Next**: Run baselines today

