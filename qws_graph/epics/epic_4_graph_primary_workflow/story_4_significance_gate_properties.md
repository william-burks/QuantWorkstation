# Story 4 — Significance Gate Properties

## ID
QWS-0407

## Status
draft

## Summary
Add `active_window_frequency`, `duty_cycle`, `first_trade_ts`, and `last_trade_ts` to
the Run node at ingest time. These properties unlock the dual-hurdle significance gate
in `promotion_candidates` (QWS-0406 Phase B) and in `QWS-0405` (promotion alerts).

## Problem
The current promotion gate checks `total_trades >= N` and `sharpe >= threshold` but has
no frequency guard. A strategy with 30 trades spread over 3 years looks statistically
similar to one with 30 trades over 6 months — but they represent fundamentally different
edges. The low-frequency strategy may be harvesting a regime-specific anomaly that appears
persistent only because the backtest window happened to contain that regime.

`active_window_frequency` closes this gap by measuring trades-per-day over the active
window only (first trade to last trade), ignoring flat periods before or after.

`duty_cycle` complements this by tracking what fraction of the backtest period had active
trading — separating "Regime Specialist" from "Robust Performer" without penalising the
frequency stat.

## Goal
At ingest time, compute and store on each Run node:

| Property | Formula | Gate |
|---|---|---|
| `first_trade_ts` | Timestamp of first closed trade in the backtest | — |
| `last_trade_ts` | Timestamp of last closed trade in the backtest | — |
| `active_window_frequency` | `total_trades / (last_trade_ts − first_trade_ts)` in trades/day | ≥ 0.06 required for promotion |
| `duty_cycle` | `active_days / total_backtest_days` | Not a gate; surfaced for context |

## Open Question — Data Availability
**Before implementing, verify:** do the current runner CSVs output `first_trade_ts` and
`last_trade_ts` (or equivalent per-trade timestamps)?

Check `research/results/futures/liquidity_sweep/runs/<timestamp>/baseline_results.csv`
for a `first_trade_date` or `start_date` column. If absent, the runner output format
must be extended before this story can proceed.

Two paths:
- **Path A** — columns already exist under a different name: add to `csv_columns` in
  `data_dictionary.yaml`, update parser. Fast.
- **Path B** — columns don't exist: extend the runner output format to include
  `first_trade_ts` and `last_trade_ts`. Requires changes to trial scripts and shell
  runners before touching the graph layer.

Resolve this before scoping implementation effort.

## In Scope
- `qws_graph/research/graph/parsers.py` — extract `first_trade_ts`, `last_trade_ts` from CSV
- `qws_graph/research/graph/store.py` — compute `active_window_frequency`, `duty_cycle` at ingest
- `qws_graph/docs/data_dictionary.yaml` — document all four new Run properties
- Unit tests: verify computation against known fixtures
- If Path B: extend runner CSV output (runner scripts + shell hooks)

## Out of Scope
- Backfilling existing Run nodes (historical runs will have null values — queries must handle null gracefully)
- Changing the promotion gate logic itself (that's QWS-0406 Phase B)
- Per-trade storage (only aggregate timestamps stored on Run)

## Repo Touchpoints
- `qws_graph/research/graph/parsers.py`
- `qws_graph/research/graph/store.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/tests/unit/test_graph_parsers.py`
- `qws_graph/tests/unit/test_store_*.py`
- *(Path B only)* `research/trials/futures/liquidity_sweep/golden.py` and sibling runners

## Acceptance Criteria
- [ ] `Run.active_window_frequency` is populated at ingest for any CSV that contains `first_trade_ts` and `last_trade_ts`.
- [ ] `Run.duty_cycle` is populated at ingest when total backtest date range is derivable.
- [ ] A CSV without `first_trade_ts` / `last_trade_ts` ingests without error; properties are null.
- [ ] `active_window_frequency` matches manual calculation: `total_trades / active_days`.
- [ ] `duty_cycle` matches manual calculation: `active_days / total_backtest_days`.
- [ ] Unit tests cover: normal case, missing columns (null handling), zero-duration edge case.
- [ ] `data_dictionary.yaml` documents all four properties with formulas and units.

## Definition of Done
- [ ] Open question on data availability resolved and documented.
- [ ] Properties computed and stored at ingest.
- [ ] Null-safe handling verified.
- [ ] Tests green.
- [ ] `data_dictionary.yaml` updated.
- [ ] Story marked CLOSED — unblocks QWS-0406 Phase B and QWS-0405.