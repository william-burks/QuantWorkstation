# Story 3 — Portfolio Correlation Analysis

## ID
QWS-0603

## Status
READY

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
preset extended with `artifact_path` in the return columns.

### CSV requirement
Each result CSV must have a `date` column and a `daily_pnl` or `equity` column.
If neither is present, the champion is skipped with a warning. This is a current CSV
format question — see Pre-condition below.

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
- `portfolio_alpha` preset extended with `artifact_path` in return columns
- Unit tests with synthetic time series
- Runbook entry

## Out of Scope
- Graph schema changes
- Real-time correlation monitoring
- Optimization of portfolio weights
- Champions without `oos_status = oos_pass` (excluded by default; configurable)

## Repo Touchpoints
- `research/analytics/portfolio_correlation.py` — new (directory also new)
- `tests/unit/test_portfolio_correlation.py` — new

## Pre-condition
Before implementing: audit the CSV column name for daily P&L by running:
`head -1 research/results/futures/*/runs/*/output.csv` (or equivalent for actual artifact
paths). If `daily_pnl` exists — implement with that name. If not, compute from trade-level
data or extend the golden run output to emit it. Document the finding in this story's
Definition of Done. This is an implementation-time discovery step, not a design blocker.

## Acceptance Criteria
- [ ] Script runs from repo root with `python -m research.analytics.portfolio_correlation`.
- [ ] Correctly computes pairwise Pearson correlation from mock daily P&L series.
- [ ] Champions whose CSVs lack a `daily_pnl`/`equity` column are skipped with a warning,
  not a crash.
- [ ] Pairs with `|r| > threshold` are flagged in output.
- [ ] Empty champion set (no OOS-pass champions) exits gracefully with a message.

## Definition of Done
- [ ] Script implemented with unit tests.
- [ ] Pre-condition CSV column discovery documented here before implementation begins.
- [ ] Story marked CLOSED.