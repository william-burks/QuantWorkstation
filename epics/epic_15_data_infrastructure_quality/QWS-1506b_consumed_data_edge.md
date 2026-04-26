# Story — CONSUMED_DATA Edge + run_data_lineage Preset

## ID
QWS-1506b

## Status
PLANNED

## Type
code

## Blocked On
QWS-1506a, QWS-1304

## Summary
Write `CONSUMED_DATA` edges from Run nodes to DataSnapshot nodes at ingest time and expose lineage via `run_data_lineage` query preset.

## Problem
Trial runs have no recorded link to the bar data they consumed. Cannot answer "what data did this Run use?" or detect when a re-reseed would invalidate a prior result.

## Goal
After `qw record --bundle` for any bundle with `data_snapshots` block: `CONSUMED_DATA` edge exists in graph; old bundles ingest cleanly; `run_data_lineage` preset returns correct data.

## Design
- `DATA_SNAPSHOT_INGEST_QUERY` in `research/graph/cypher.py`: MERGE on `content_hash`, SET all DataSnapshot properties
- `CONSUMED_DATA_EDGE_QUERY` in `research/graph/cypher.py`: MERGE `(:Run {run_id: $run_id})-[:CONSUMED_DATA]->(:DataSnapshot {content_hash: $content_hash})`
- `GraphStore.write_data_snapshot(run_id: str, snapshots: list[DataSnapshot])` in `research/graph/store.py` — writes nodes + edges in a single transaction
- `_cmd_bundle()` in `research/graph/cli.py` — after CSV ingest, reads `data_snapshots` from manifest, calls `Store.snapshot_id()` per entry, calls `GraphStore.write_data_snapshot()`
- `qw record --bundle` fails (non-zero exit, stderr message) if ArcticDB read returns empty for a declared snapshot spec
- `run_data_lineage` preset in `research/graph/query_presets.py` — returns Run node + linked DataSnapshot hashes + symbol + date range
- `docs/PROVENANCE_ENGINE.md` gains `DataSnapshot` node section (properties, ID convention) and `CONSUMED_DATA` edge section

## In Scope
- `research/graph/cypher.py` — add `DATA_SNAPSHOT_INGEST_QUERY`, `CONSUMED_DATA_EDGE_QUERY`
- `research/graph/store.py` — add `GraphStore.write_data_snapshot(run_id, snapshots)`
- `research/graph/cli.py` — update `_cmd_bundle()` to write DataSnapshot nodes + CONSUMED_DATA edges after CSV ingest
- `research/graph/query_presets.py` — add `run_data_lineage` preset
- `docs/PROVENANCE_ENGINE.md` — add DataSnapshot node section and CONSUMED_DATA edge section

## Repo Touchpoints
- `research/graph/cypher.py` — `DATA_SNAPSHOT_INGEST_QUERY`; `CONSUMED_DATA_EDGE_QUERY`
- `research/graph/store.py` — `GraphStore.write_data_snapshot(run_id: str, snapshots: list[DataSnapshot])`
- `research/graph/cli.py` — `_cmd_bundle()` updated; non-zero exit if empty ArcticDB read for declared snapshot
- `research/graph/query_presets.py` — `run_data_lineage` preset
- `docs/PROVENANCE_ENGINE.md` — DataSnapshot node section + CONSUMED_DATA edge section

## Acceptance Criteria
- [ ] `CONSUMED_DATA` edge exists in graph after `qw record --bundle` for any bundle with `data_snapshots` block
- [ ] Old bundles (no `data_snapshots` block) ingest cleanly — no error, no edge written
- [ ] `qw record --bundle` exits non-zero with clear stderr if declared symbol/range returns empty from ArcticDB
- [ ] `run_data_lineage` preset returns correct Run + snapshot data
- [ ] Test: reseed a symbol, re-ingest same trial → new DataSnapshot node written; original Run's `CONSUMED_DATA` edge still resolves to original snapshot hash (old node preserved)
- [ ] `PROVENANCE_ENGINE.md` DataSnapshot and CONSUMED_DATA sections complete with all properties and ID convention

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: CONSUMED_DATA edge written after bundle ingest
- type: integration
- cmd: `source .venv/bin/activate && pytest tests/integration/test_consumed_data_edge.py -k "edge_written" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC2: old bundle ingests cleanly
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_cli_bundle.py -k "old_bundle_no_snapshots" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: empty ArcticDB read → non-zero exit
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_cli_bundle.py -k "empty_arcticdb_nonzero" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: run_data_lineage preset returns data
- type: cli
- cmd: `source .venv/bin/activate && qw query --name run_data_lineage 2>&1 | head -10`
- expect_exit: 0

### AC5: reseed → new snapshot node, old edge preserved
- type: integration
- cmd: `source .venv/bin/activate && pytest tests/integration/test_consumed_data_edge.py -k "reseed_preserves_old_node" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC6: PROVENANCE_ENGINE.md updated
- type: file_check
- cmd: `grep -n "DataSnapshot\|CONSUMED_DATA" docs/PROVENANCE_ENGINE.md`
- expect_contains: "DataSnapshot"
- expect_contains: "CONSUMED_DATA"
- expect_exit: 0
