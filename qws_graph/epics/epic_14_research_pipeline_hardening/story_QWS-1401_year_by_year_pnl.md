# Story — Year-by-Year P&L in Trial Output

## ID
QWS-1401

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add annual P&L breakdown table to `evaluator.py` report() output. Auto-flag regime concentration when any single year exceeds 50% of total gross profit.

## Problem
Trial reports show aggregate IS metrics only. A strategy with 80% of gross profit in one year (e.g. 2020 COVID crash) looks identical to a diversified strategy. Regime concentration is invisible until manual inspection.

## Goal
After this story, every `report()` call prints:

```
Annual Breakdown
Year  | Trades | Gross P&L | Sharpe | % of Total
------+--------+-----------+--------+-----------
2020  |     42 |   $12,400 |   3.21 |      61.2%
2021  |     38 |    $5,800 |   1.87 |      28.7%
2022  |     19 |    $2,050 |   1.44 |      10.1%

[WARN] Regime concentration: 2020 = 61.2% of profit
```

## Design

### evaluator.py changes
- `report()` calls new `_annual_breakdown(equity_curve, trades_df) -> pd.DataFrame`
- `_annual_breakdown` groups trades by year, computes: trade count, gross P&L, per-year Sharpe, pct of total gross P&L
- Appends formatted table to existing report string — after aggregate metrics block
- Concentration check: if any row `pct > 50`, appends `[WARN] Regime concentration: {year} = {pct:.1f}% of profit`

### metrics.py changes
- Add `annual_pnl_breakdown(trades_df) -> list[dict]` — raw data, no formatting
- Returns: `[{"year": int, "trades": int, "gross_pnl": float, "sharpe": float, "pct_of_total": float}]`

## In Scope
- `research/experiments/evaluator.py` — `report()` + `_annual_breakdown()`
- `research/experiments/metrics.py` — `annual_pnl_breakdown()`
- Unit tests: single year, multi-year, concentration threshold fires at exactly 50.0001%, does not fire at 50.0%

## Out of Scope
- OOS breakdown — IS only for now
- Graph writes — no schema changes
- Diversity gate — QWS-1402

## Repo Touchpoints
- `research/experiments/evaluator.py`
- `research/experiments/metrics.py`
- `tests/unit/test_annual_breakdown.py` — new

## Acceptance Criteria
- [x] `report()` output includes annual breakdown table after existing aggregate block
- [x] Concentration warning fires when any year > 50% of total gross profit
- [x] Concentration warning does NOT fire when max year = 50.0% exactly
- [x] Existing report output (aggregate metrics, signal stats) unchanged
- [x] `annual_pnl_breakdown()` returns correct values for synthetic trades fixture
- [x] `make verify` passes with no new violations

## Definition of Done
- [x] `evaluator.py` updated
- [x] `metrics.py` updated
- [x] Unit tests pass
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: annual breakdown table appears after aggregate block
- type: file_check
- cmd: `source .venv/bin/activate && pytest tests/unit/test_annual_breakdown.py::TestAnnualBreakdownFormatter::test_header_present -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC2: Concentration warning fires when year > 50%
- type: file_check
- cmd: `source .venv/bin/activate && pytest tests/unit/test_annual_breakdown.py::TestAnnualBreakdownFormatter::test_concentration_fires_above_50 -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC3: Concentration warning does NOT fire at exactly 50%
- type: file_check
- cmd: `source .venv/bin/activate && pytest tests/unit/test_annual_breakdown.py::TestAnnualBreakdownFormatter::test_concentration_does_not_fire_at_exactly_50 -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: Existing report output unchanged (no trades_df arg)
- type: regression
- cmd: `source .venv/bin/activate && python -c "import inspect; from research.experiments.evaluator import report; sig = inspect.signature(report); params = list(sig.parameters); assert params[:5] == ['results','bh','metadata','top_n','full_n'], params"`
- expect_contains: ""
- expect_exit: 0

### AC5: annual_pnl_breakdown returns correct values
- type: file_check
- cmd: `source .venv/bin/activate && pytest tests/unit/test_annual_breakdown.py::TestAnnualPnlBreakdown -v`
- expect_contains: "6 passed"
- expect_exit: 0

### AC6: Full suite passes
- type: file_check
- cmd: `source .venv/bin/activate && pytest tests/unit/test_annual_breakdown.py -v`
- expect_contains: "12 passed"
- expect_exit: 0
