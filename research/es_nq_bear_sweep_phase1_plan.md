# ES/NQ Bear Sweep — Phase 1 Research Plan

**Date**: April 1, 2026  
**Status**: Pre-baseline  
**Confidence**: Untested hypothesis

---

## Baseline Execution

Two baseline scripts are ready for immediate use:

```zsh
# ES baseline — all sessions, no wick filter, target_r=1.25
cd /Users/will/ClaudeProjects/QuantWorkstation
python strategies/bear_es_sweep_1h_baseline.py

# NQ baseline — all sessions, no wick filter, target_r=1.25
python strategies/bear_nq_sweep_1h_baseline.py
```

### What the Baseline Measures

Each baseline run will produce:
- **Sweeps total**: Count of 1H bars exceeding a prior swing high then closing back inside
- **Confirmation funnel**: How many sweeps → BOS/IFVG on 5m → entry confirmed
- **Trade sample**: Count of trades that emerged from confirmation chain
- **Win rate, avg_r, sharpe, max_dd**: Performance metrics on all sessions
- **Session breakdown**: Which sessions (NY_PRE, AFTER, LONDON, ASIA, NY) carry the signal

### Decision Gate for Phase 1

| Outcome | Action |
|---|---|
| n ≥ 20, win_rate ≥ breakeven, sharpe > 0 | Proceed to Phase 3 grid search (signal is present) |
| n ≥ 20, win_rate < breakeven but n > 10 | Proceed to Phase 2 isolation (find which sessions matter) |
| n < 20 | Below minimum. Hypothesis may be too constrained. Document and retry with relaxed parameters. |
| n ≥ 20, win_rate << breakeven | Stop. Document failure. The sweep-reverse pattern does not carry on this instrument. |

---

## Key Hypotheses at Stake

1. **Retail stop clustering is universal** across instruments. Equity index futures have different participant bases (dark pools, index rebalancing) than commodities — sweeps may not create predictable reversals.

2. **1H is the right timeframe** for swing detection on ES/NQ. If sweeps are too frequent or too sparse, adjust swing_n or use 4H.

3. **NY_PRE is the strongest session**. Pre-market on equities may be dominated by gap fills, not sweep reversals — weaker than CL.

4. **London open carries signal on equities**. This is entirely new — CL excluded LONDON, but equity index futures may show stronger London reversals.

5. **0.5 ATR stop buffer scales correctly**. ES/NQ have different tick sizes and spreads; the stop may be too tight or too loose.

---

## Phase 2 Isolation (if Baseline Passes Gate)

If baseline shows win_rate < breakeven but n ≥ 20, run one isolation test at a time:

### Test 2.1: Session Filter
```zsh
python strategies/bear_es_sweep_1h_baseline.py --allowed_sessions NY_PRE
python strategies/bear_es_sweep_1h_baseline.py --allowed_sessions LONDON
python strategies/bear_es_sweep_1h_baseline.py --allowed_sessions AFTER
python strategies/bear_es_sweep_1h_baseline.py --allowed_sessions NY_PRE,AFTER
python strategies/bear_es_sweep_1h_baseline.py --allowed_sessions LONDON,NY_PRE
```

Record for each: n, win_rate, avg_r, sharpe. Identify which session(s) show improvement over baseline.

### Test 2.2: ATR Stop Buffer
If sessions show mixed results, test stop buffer calibration:
```zsh
python strategies/bear_es_sweep_1h_baseline.py --atr-mult-stop 0.3
python strategies/bear_es_sweep_1h_baseline.py --atr-mult-stop 0.5
python strategies/bear_es_sweep_1h_baseline.py --atr-mult-stop 0.7
```

### Test 2.3: Wick Mode
If wick size quartiles (from baseline report) show Q3/Q4 outperforming Q1/Q2:
```zsh
python strategies/bear_es_sweep_1h_baseline.py --wick-mode exclude_q2
python strategies/bear_es_sweep_1h_baseline.py --wick-mode q3_q4_only
```

---

## Phase 3 Grid Search (if Baseline Passes Gate or Phase 2 Isolation Succeeds)

Once an isolated signal is found, run a 2-axis grid:

```zsh
python strategies/bear_es_sweep_1h_baseline.py --grid \
  --target-r-grid "1.0,1.25,1.5,1.75" \
  --wick-modes "none,exclude_q2,q3_q4_only" \
  --atr-mult-stop-grid "0.3,0.5,0.7" \
  --allowed-sessions "NY_PRE,AFTER" \
  --results-csv "results/es_bear_sweep_1h_grid_v1.csv"
```

The grid will:
1. Run all combinations of the axes
2. Save results to CSV
3. Print top 10 configs by Sharpe
4. Identify champion (highest Sharpe among configs passing gates)

### Minimum Gates for Champion Promotion
- Sample size: ≥ 20
- Total R: > 0
- Profit factor: ≥ 1.10
- Max drawdown: ≥ -12R

---

## What Success Looks Like

If baseline passes with n ≥ 20, win_rate ≥ breakeven, sharpe > 1.5:
- **ES**: Directly promote to Phase 4 (freeze champion)
- **NQ**: Also passes → compare ES vs NQ trade correlation. If uncorrelated, both can be run in portfolio.

If baseline shows n < 20 or win_rate < breakeven:
- Phase 2 isolation to find the session(s) that carry the edge
- Use wick and ATR filters to clean up noise
- Re-test in Phase 3 grid with motivated axes only

---

## Important: Data Assumptions

Both baseline scripts use **MES/MNQ data** (you don't need ES/NQ separately):
- **ES baseline** uses: `MES_continuous_5min.parquet` and `MES_continuous_1H.parquet` (required)
  - Optionally uses `MNQ_continuous_5min.parquet` for SMT divergence
- **NQ baseline** uses: `MNQ_continuous_5min.parquet` and `MNQ_continuous_1H.parquet` (required)
  - Optionally uses `MES_continuous_5min.parquet` for SMT divergence

MES and MNQ work identically to ES and NQ for detecting the sweep pattern. If SMT data is missing, scripts gracefully fall back (SMT is not core to the signal anyway).

Location: `/Users/will/quant-research/data/futures/`

---

## Session Checklist Before Phase 2

- [ ] Both baseline scripts ran successfully
- [ ] Baseline reports saved and reviewed
- [ ] Session breakdown table shows which sessions matter
- [ ] Wick quartile table shows if small/large wicks matter
- [ ] Decision: Phase 2 isolation or Phase 3 grid?
- [ ] Documented the baseline result in research/notes/


