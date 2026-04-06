# Story 3 — Portfolio Correlation Analysis

## ID
QWS-0603

## Status
draft

## Summary
A Python analytics script (`research/analytics/portfolio_correlation.py`) that reads
`artifact_path` from all current OOS-pass Champions, loads their result CSVs, computes
a pairwise correlation matrix of daily P&L, and flags high-correlation pairs as
concentration risk.

## Problem
The graph has a `portfolio_alpha` query that aggregates champion metrics, but it cannot
detect when two champions blow up simultaneously — that requires time-series correlation,
which lives in CSV files, not graph properties.

Trading all current champions at once without checking correlation creates hidden
concentration risk: strategies that look independent by instrument may be driven by the
same macro factor and drawdown together.

## Architecture
The graph is an index; Python does the computation.

```
qw query --name portfolio_alpha → champion list with artifact_paths
↓
read CSV for each champion (daily equity or trade P&L)
↓
pandas correlation matrix
↓
flag pairs with |correlation| > threshold
```

## Design

### Input
All Champions where `oos_status = oos_pass`. Retrieved via the existing `portfolio_alpha`
preset extended with `artifact_path` in the return columns, or via a new
`champion_artifacts` preset (minimal Cypher addition).

### CSV requirement
Each result CSV must have a `date` column and a `daily_pnl` or `equity` column.
If neither is present, the champion is skipped with a warning. This is a current CSV
format question — verify against actual output before implementing.

### Output
```
Portfolio Correlation Report (4 champions)
──────────────────────────────────────────
                     cl-bear  btc-bull  es-bear  nq-bear
cl-1h-bear-ls         1.00     0.12     0.71*    0.08
btc-1d-bull-mars      0.12     1.00     0.15     0.22
es-1h-bear-ls         0.71*    0.15     1.00     0.63*
nq-1h-bear-ls         0.08     0.22     0.63*    1.00

* HIGH CORRELATION (|r| > 0.60) — concentration risk
  CL bear ↔ ES bear: r=0.71  [review before running together]
  ES bear ↔ NQ bear: r=0.63  [expected — same index family]
```

### Threshold
Default `|correlation| > 0.60` flagged as high. Configurable via `--threshold`.

## Deliverable
- `research/analytics/portfolio_correlation.py`
- CLI: `python -m research.analytics.portfolio_correlation [--threshold 0.6]`
- Unit tests with mock CSV data

## In Scope
- `research/analytics/portfolio_correlation.py`
- Minimal graph query to retrieve OOS-pass champion `artifact_path` values
- Unit tests with synthetic time series
- Runbook entry

## Out of Scope
- Graph schema changes
- Real-time correlation monitoring
- Optimization of portfolio weights
- Champions without `oos_status = oos_pass` (excluded by default; configurable)

## Acceptance Criteria
- [ ] Script runs from repo root with `python -m research.analytics.portfolio_correlation`.
- [ ] Correctly computes pairwise Pearson correlation from mock daily P&L series.
- [ ] Champions whose CSVs lack a `daily_pnl`/`equity` column are skipped with a warning,
  not a crash.
- [ ] Pairs with `|r| > threshold` are flagged in output.
- [ ] Empty champion set (no OOS-pass champions) exits gracefully with a message.

## Open Question
What column name does the result CSV use for daily P&L? Audit existing CSV output from
`run_liquidity_sweep_golden.sh` before implementing. If daily P&L isn't in the CSV,
the story needs a pre-condition: extend golden run output to include it, or compute from
trade-level data.

## Definition of Done
- [ ] Script implemented with unit tests.
- [ ] Open question on CSV column format resolved and documented.
- [ ] Story marked CLOSED.
