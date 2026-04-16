# Story — Regime Diversity Gate

## ID
QWS-1402

## Status
READY

## Type
code

## Blocked On
QWS-1401

## Summary
Compute regime diversity score from annual breakdown (QWS-1401). Warn — do not reject — when IS trades span fewer than 3 distinct years or fewer than 2 years with positive P&L. Write diversity score to existing `trial_metadata` map on Run node.

## Problem
A strategy passing IS Sharpe ≥ 2.0 with all trades in one regime year is a fragile champion candidate. The pipeline has no gate that surfaces this risk before `qw record --bundle`.

## Goal
After this story:
1. `report()` prints diversity score and fires warning when below threshold
2. `qw record --bundle` prints the same warning before ingestion (advisory only — ingest proceeds)
3. `trial_metadata` map on Run node contains `diversity_score` and `diversity_years_positive`

## Design

### Diversity score definition
```
diversity_score = distinct_profitable_years / total_distinct_years
```
- `distinct_years` = count of calendar years with ≥1 trade
- `distinct_profitable_years` = count of years with gross P&L > 0
- Score range: [0.0, 1.0]

### Gate thresholds
- WARN if `distinct_years < 3`
- WARN if `distinct_profitable_years < 2`
- Advisory only — no auto-rejection at any threshold

### evaluator.py additions
- `_diversity_score(annual_breakdown_df) -> dict` — computes score fields
- `report()` appends diversity block after annual breakdown:
  ```
  Regime Diversity
  Score: 0.67 | Years traded: 3 | Profitable years: 2
  [WARN] Diversity: only 3 years of IS trades — consider extending backtest window
  ```
- evaluator writes `diversity_score`, `diversity_years_positive`, `diversity_distinct_years` into bundle.json alongside existing grid CSV metadata — single computation per trial run

### qw record --bundle
- After bundle validation, before Neo4j write: reads pre-computed diversity fields from bundle.json; prints warning if below threshold
- Does NOT recompute diversity from raw trade data — reads evaluator-computed fields only
- Writes `diversity_score`, `diversity_years_positive`, `diversity_distinct_years` into `trial_metadata` map on Run node (existing map — no schema change)
- `metrics.diversity_score()` is called only by evaluator — not by ingest

### metrics.py
- `diversity_score(annual_breakdown: list[dict]) -> dict` — pure function, no side effects

## In Scope
- `research/experiments/evaluator.py` — `_diversity_score()`, `report()` additions
- `research/experiments/metrics.py` — `diversity_score()`
- `qws_graph/ingest/bundle_ingest.py` (or equivalent bundle ingest path) — diversity warning + trial_metadata write
- Unit tests: score computation, gate fires below threshold, gate silent at/above threshold, trial_metadata keys present after ingest

## Out of Scope
- Auto-rejection
- OOS diversity score
- New graph node types or edge types

## Repo Touchpoints
- `research/experiments/evaluator.py`
- `research/experiments/metrics.py`
- `qws_graph/ingest/bundle_ingest.py` (verify exact path before edit)
- `tests/unit/test_diversity_gate.py` — new

## Acceptance Criteria
- [ ] `diversity_score()` returns correct dict for synthetic annual_breakdown fixture
- [ ] `report()` prints diversity block with score, years traded, profitable years
- [ ] Warning fires when `distinct_years < 3` OR `distinct_profitable_years < 2`
- [ ] Warning silent when both thresholds met
- [ ] `qw record --bundle` prints diversity warning when below threshold
- [ ] `bundle.json` includes `diversity_score`, `diversity_years_positive`, `diversity_distinct_years` fields after trial run
- [ ] `qw record --bundle` reads diversity fields from bundle.json (does not recompute)
- [ ] `trial_metadata` on ingested Run node contains `diversity_score`, `diversity_years_positive`, `diversity_distinct_years`
- [ ] No auto-rejection — ingest proceeds regardless of diversity score
- [ ] `make verify` passes with no new violations

## Definition of Done
- [ ] `evaluator.py` updated
- [ ] `metrics.py` updated
- [ ] Bundle ingest path updated
- [ ] Unit tests pass
- [ ] Story marked CLOSED
