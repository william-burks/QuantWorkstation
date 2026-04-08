# Story 4 — Significance Gate Properties

## ID
QWS-0407

## Status
CLOSED

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

## Data Availability — Resolved: Path B
Runner CSVs do **not** contain `first_trade_ts`, `last_trade_ts`, or any equivalent column.
Confirmed by inspecting `qws_graph/docs/data_dictionary.yaml` (lines 774–788) and actual
CSV headers (`research/results/crypto/mars/runs/.../baseline_results.csv` has no timestamp
columns beyond the row-level `timestamp` optional field).

**Path B is required:** runner output format must be extended to emit `first_trade_ts` and
`last_trade_ts` before the graph layer can compute `active_window_frequency` and `duty_cycle`.
This means runner scripts (golden.py and sibling runners) must be updated as part of this story.

## In Scope
- `qws_graph/research/graph/parsers.py` — extract `first_trade_ts`, `last_trade_ts` from CSV
- `qws_graph/research/graph/store.py` — compute `active_window_frequency`, `duty_cycle` at ingest
- `qws_graph/docs/data_dictionary.yaml` — document all four new Run properties
- `research/experiments/standards.py` — add `MIN_ACTIVE_WINDOW_FREQUENCY: float = 0.06` constant so QWS-0405 can import it
- Extend runner CSV output: runner scripts must emit `first_trade_ts` and `last_trade_ts` (Path B)
- Unit tests: verify computation against known fixtures

## Out of Scope
- Backfilling existing Run nodes (historical runs will have null values — queries must handle null gracefully)
- Changing the promotion gate logic itself (that's QWS-0406 Phase B)
- Per-trade storage (only aggregate timestamps stored on Run)

## Repo Touchpoints
- `qws_graph/research/graph/parsers.py`
- `qws_graph/research/graph/store.py`
- `qws_graph/docs/data_dictionary.yaml`
- `research/experiments/standards.py`
- `qws_graph/tests/unit/test_graph_parsers.py`
- `qws_graph/tests/unit/test_store_*.py`
- `research/trials/futures/liquidity_sweep/golden.py` — new columns required
- `research/trials/futures/liquidity_sweep/01_baseline.py` — new columns required
- `research/trials/futures/liquidity_sweep/02_position_sizing.py` — new columns required

## Acceptance Criteria
- [x] `Run.active_window_frequency` is populated at ingest for any CSV that contains `first_trade_ts` and `last_trade_ts`.
- [x] `Run.duty_cycle` is populated at ingest when `backtest_start` and `backtest_end` are present; null otherwise.
- [x] A CSV missing `first_trade_ts` or `last_trade_ts` fails parse with a clear error (required columns).
- [x] `active_window_frequency` matches manual calculation: `total_trades / active_days`.
- [x] `duty_cycle` matches manual calculation: `active_days / total_backtest_days`.
- [x] Unit tests cover: normal case, missing required columns (parse error), zero-duration edge case (active_window_frequency is null).
- [x] `data_dictionary.yaml` documents all four properties with formulas and units.

## Acceptance Criteria (additional)
- [x] `MIN_ACTIVE_WINDOW_FREQUENCY = 0.06` constant exists in `research/experiments/standards.py`.
- [x] `research/trials/futures/liquidity_sweep/golden.py` CSV output includes `first_trade_ts` and `last_trade_ts` columns.

## Definition of Done
- [x] Path B confirmed and documented — runner CSV output extended.
- [x] Properties computed and stored at ingest.
- [x] Null-safe handling verified.
- [x] Tests green.
- [x] `data_dictionary.yaml` updated.
- [x] `MIN_ACTIVE_WINDOW_FREQUENCY` constant added to `standards.py`.
- [x] Story marked CLOSED — unblocks QWS-0406 Phase B and QWS-0405.