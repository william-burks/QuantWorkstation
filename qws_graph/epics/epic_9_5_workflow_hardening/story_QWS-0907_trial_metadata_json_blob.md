# Story 3 — Custom trial metadata persisted on Run node

## ID
QWS-0907

## Status
TESTING

## Type
schema

## Blocked On
None

## Summary
Add `trial_metadata` map property to Run node so regime-conditioning custom columns (`atr_bucket`, `regime_label`, etc.) survive bundle ingest instead of being silently discarded.

## Problem
Trial scripts write custom columns to results CSV. `qw record --bundle` emits WARNING and discards them. Regime conditioning work loses per-bucket data permanently — `atr_bucket`, `avg_atr`, `regime_label` are gone after ingest.

## Goal
`bundle.json` manifest accepts `trial_metadata` dict. After `qw record --bundle`, property queryable via Cypher: `MATCH (r:Run {run_id: $id}) RETURN r.trial_metadata.atr_bucket`. Unknown CSV columns still warn (unchanged behavior).

## Schema Extension
| Element | Type | Properties | Notes |
|---|---|---|---|
| `Run` | Node | `trial_metadata: map` | additive, nullable |

Precedent: `Config.params_json` existing map property pattern.

All additions must be registered in `qws_graph/docs/data_dictionary.yaml`.

## In Scope
- `trial_metadata` map property on Run node (additive, nullable)
- `bundle.json` manifest schema accepts top-level `trial_metadata` key (key-value dict, string values)
- `qw record --bundle` reads `trial_metadata` from manifest and writes to Run node after ingest
- 10KB size guard at ingest: if `json.dumps(trial_metadata)` exceeds 10240 bytes, print WARNING and skip `trial_metadata` write; ingest continues and succeeds
- Unknown CSV columns continue to emit WARNING (no change)
- `data_dictionary.yaml` updated with `trial_metadata` entry
- `PROVENANCE_ENGINE.md` Run Key Properties table updated with `trial_metadata` entry

## Out of Scope
- No `trial_metadata` on non-Run nodes
- No CLI flag to set `trial_metadata` outside of bundle ingest
- No validation of `trial_metadata` key names (free-form)
- No CSV column → `trial_metadata` auto-mapping

## Repo Touchpoints
<!-- MAX 5 FILES. If you need more, split the story. -->
- `qws_graph/docs/data_dictionary.yaml` — add `trial_metadata` to Run entry
- `qws_graph/research/graph/store.py` — write `trial_metadata` map on `record_run()`
- `qws_graph/research/graph/cli.py` — pass `trial_metadata` from parsed manifest to store
- `docs/PROVENANCE_ENGINE.md` — add `trial_metadata` to Run Key Properties table
- `qws_graph/tests/unit/test_bundle_metadata.py` — new

## Acceptance Criteria
- [x] Bundle with `trial_metadata: {atr_bucket: "high", avg_atr: "2.3"}` → property present on Run node, queryable via `r.trial_metadata.atr_bucket`
- [x] Bundle without `trial_metadata` field → ingest succeeds, `trial_metadata` absent on node (no error)
- [x] Bundle with `trial_metadata` > 10KB → WARNING printed, ingest succeeds, `trial_metadata` absent on node
- [x] Unknown CSV columns still emit WARNING (behavior unchanged)
- [x] `data_dictionary.yaml` has `trial_metadata` entry under `Run`
- [x] `PROVENANCE_ENGINE.md` Run Key Properties table includes `trial_metadata`

## Definition of Done
- [x] data_dictionary.yaml updated
- [x] Tests green
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: Bundle with trial_metadata → write_trial_metadata called with correct dict
- type: regression
- cmd: `pytest qws_graph/tests/unit/test_bundle_metadata.py::TestTrialMetadataWritten -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC2: Bundle without trial_metadata → write_trial_metadata not called
- type: regression
- cmd: `pytest qws_graph/tests/unit/test_bundle_metadata.py::TestTrialMetadataAbsent -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC3: Bundle with trial_metadata > 10KB → WARNING, no write
- type: regression
- cmd: `pytest qws_graph/tests/unit/test_bundle_metadata.py::TestTrialMetadataSizeGuard -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4 (store method): TRIAL_METADATA_WRITE_QUERY used, correct params, empty list skips
- type: regression
- cmd: `pytest qws_graph/tests/unit/test_bundle_metadata.py::TestWriteTrialMetadataStore -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: data_dictionary.yaml has trial_metadata entry
- type: file_check
- cmd: `grep -c 'trial_metadata' qws_graph/docs/data_dictionary.yaml`
- expect_contains: "1"
- expect_exit: 0

### AC6: PROVENANCE_ENGINE.md has trial_metadata in Run table
- type: file_check
- cmd: `grep -c 'trial_metadata' docs/PROVENANCE_ENGINE.md`
- expect_contains: "1"
- expect_exit: 0
