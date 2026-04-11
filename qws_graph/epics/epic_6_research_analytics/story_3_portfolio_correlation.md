# Story 3 — Portfolio Correlation Analysis

## ID
QWS-0603

## Status
READY

## Summary
Introduces `CORRELATED_WITH` edges between Strategy/Champion nodes, extends the
`portfolio_alpha` preset with MaxDD and Calmar ratio filters, adds a correlation gate
on the Champion promotion path, and ships a Python analytics script
(`research/analytics/portfolio_correlation.py`) that computes the pairwise correlation
matrix and writes results back to the graph.

## Problem
The graph has a `portfolio_alpha` query that aggregates champion metrics, but it cannot
detect when two champions blow up simultaneously — that requires time-series correlation,
which lives in CSV files, not graph properties.

Trading all current champions at once without checking correlation creates hidden
concentration risk: strategies that look independent by instrument may be driven by the
same macro factor and drawdown together.

## Architecture
Graph holds schema and results; Python does computation.

```
qw query --name portfolio_alpha → champion list with artifact_paths + MaxDD/Calmar
↓
read CSV for each champion (daily equity or trade P&L)
↓
pandas correlation matrix
↓
flag pairs with |correlation| > threshold
↓
write CORRELATED_WITH edges back to graph (Champion–Champion and Strategy–Strategy)
```

Promotion path: the auto-promote step inside `qw record --bundle` checks existing
`CORRELATED_WITH` edges before creating a new Champion. If the candidate correlates
above threshold with an active Champion, promotion emits a warning (non-blocking by
default; configurable to block).

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
- `CORRELATED_WITH` edge in `store.py` (Champion→Champion and Strategy→Strategy)
- `portfolio_alpha` preset extended with `artifact_path`, MaxDD, Calmar ratio, and `is_oos_drift` flag (True when `oos_sharpe` deviates from IS Sharpe by >20%) in return columns
- Correlation gate in `qw record --bundle` auto-promote path — warns (non-blocking) when candidate correlates above threshold with active Champion
- Unit tests with synthetic time series
- Runbook entry

## Out of Scope
- Blocking promotion on correlation (warning only unless user configures `--strict`)
- Real-time correlation monitoring
- Optimization of portfolio weights
- Champions without `oos_status = oos_pass` (excluded by default; configurable)
- `SEMANTICALLY_RELATED` edges (QWS-0604)

## Repo Touchpoints
- `research/analytics/portfolio_correlation.py` — new (directory also new)
- `qws_graph/research/graph/store.py` — `CORRELATED_WITH` edge write method
- `qws_graph/research/graph/query_presets.py` — `portfolio_alpha` MaxDD/Calmar extension
- `qws_graph/research/graph/cli.py` — correlation gate hook in `qw record --bundle` auto-promote path
- `qws_graph/docs/data_dictionary.yaml` — `CORRELATED_WITH` edge entry
- `qws_graph/docs/graph_v1_contract.md` — schema update
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
- [ ] Script writes `CORRELATED_WITH` edges to graph for each flagged pair after computation.
- [ ] `qw query --name portfolio_alpha` returns MaxDD and Calmar ratio columns alongside existing metrics.
- [ ] `portfolio_alpha` flags Champions where `oos_sharpe` deviates from IS Sharpe by more than 20% with `is_oos_drift=True` in the result row.
- [ ] `qw record --bundle` auto-promote path emits a correlation warning when candidate Champion has `CORRELATED_WITH` edge to an active Champion above threshold.
- [ ] `data_dictionary.yaml` and `graph_v1_contract.md` include `CORRELATED_WITH` edge definition.

## Definition of Done
- [ ] Script implemented with unit tests.
- [ ] `CORRELATED_WITH` edge write method implemented and tested.
- [ ] `portfolio_alpha` preset updated with MaxDD, Calmar, and `is_oos_drift` columns.
- [ ] Correlation gate check implemented in `qw record --bundle` auto-promote path.
- [ ] Schema docs updated (`data_dictionary.yaml`, `graph_v1_contract.md`).
- [ ] Pre-condition CSV column discovery documented here before implementation begins.
- [ ] Story marked CLOSED.