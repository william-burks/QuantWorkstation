# Story — Bitemporal as_of on Runs

## ID
QWS-1509

## Status
PLANNED

## Type
code

## Blocked On
QWS-1506a, QWS-1304

## Summary
Record the data knowledge-time cutoff (`data_as_of`) on every Run node so vendor revisions cannot silently change backtest comparisons.

## Problem
CONTFUT is as-of today. Re-backtest in 2026 uses a 2026 ratio chain — look-ahead is embedded in the adjustment itself. No record of what the data state was when a trial ran. `stale_data_runs` and `run_data_lineage` presets cannot identify Runs that consumed stale data.

## Goal
`data_as_of` written to Run node when DataSnapshot nodes exist; Runs with no CONSUMED_DATA edges get `data_as_of = null`; `stale_data_runs` preset returns Runs where `data_as_of` is older than configurable threshold before `run_ts`.

## Design
- `data_as_of = max(snapshot.snapshot_ts for snapshots linked via CONSUMED_DATA)` — computed during ingest from linked DataSnapshot nodes; OR set explicitly from `bundle.json` `data_as_of` field if no snapshots (backwards compat path)
- Add `data_as_of: Optional[datetime] = None` to `Run` model in `research/graph/models.py`
- `stale_data_runs` preset threshold: `data_as_of < (run_ts - threshold_days)` — threshold configurable as preset parameter (default 30 days)
- Investigation required at kickoff: crypto collector does not currently emit `knowledge_time`. Databento pipeline does via `as_of`. Determine whether crypto collector needs a `collected_at` timestamp field added to bar metadata for QWS-1509 to be meaningful for crypto symbols.

## In Scope
- `research/graph/models.py` — add `data_as_of: Optional[datetime] = None` to `Run` model
- `research/graph/cli.py` — update `_cmd_bundle()` to compute `data_as_of` from linked DataSnapshot `snapshot_ts` values after ingest
- `research/graph/cypher.py` — update `CSV_INGEST_QUERY` SET clause for `data_as_of`
- `research/graph/query_presets.py` — add `stale_data_runs` preset with configurable threshold

## Repo Touchpoints
- `research/graph/models.py` — `data_as_of: Optional[datetime] = None` on `Run`
- `research/graph/cli.py` — `_cmd_bundle()` computes `data_as_of` from linked DataSnapshot nodes after ingest
- `research/graph/cypher.py` — `CSV_INGEST_QUERY` SET clause updated for `data_as_of`
- `research/graph/query_presets.py` — `stale_data_runs` preset

## Acceptance Criteria
- [ ] `data_as_of` written to Run node after ingest when DataSnapshot nodes exist
- [ ] Runs with no CONSUMED_DATA edges get `data_as_of = null` — no error
- [ ] `stale_data_runs` preset returns Runs where `data_as_of` is older than threshold before `run_ts`; example Cypher: `MATCH (r:Run) WHERE r.data_as_of < datetime() - duration({days: 30}) RETURN r LIMIT 10`
- [ ] Test: ingest Run with DataSnapshot timestamped 45 days before run_ts → appears in `stale_data_runs` at 30-day threshold

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: data_as_of written when DataSnapshot nodes exist
- type: integration
- cmd: `source .venv/bin/activate && pytest tests/integration/test_bitemporal.py -k "data_as_of_written" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC2: no CONSUMED_DATA → data_as_of null, no error
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_bitemporal.py -k "no_snapshots_null" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: stale_data_runs preset returns correct results
- type: cli
- cmd: `source .venv/bin/activate && qw query --name stale_data_runs 2>&1 | head -5`
- expect_exit: 0

### AC4: 45-day-old snapshot appears in 30-day threshold preset
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_bitemporal.py -k "stale_45day_appears" -v 2>&1 | tail -5`
- expect_contains: "passed"
