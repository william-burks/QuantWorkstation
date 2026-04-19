# Story — family_id Backfill Migration

## ID
## QWS-0210C

## Status
CLOSED

## Priority
P3 — Research Quality. Pre-existing Strategy nodes in the graph have `family_id = null` and
will fall back to the `logic_type + direction` correlation axis. This is acceptable at low node
counts but degrades cross-artifact correlation accuracy as the graph grows. Backfill before the
node count exceeds ~20 strategies.

## Summary
Re-ingest existing Strategy nodes with `--source-file` to populate `family_id` on pre-existing
nodes. Provides a migration Cypher query for any nodes that cannot be re-ingested (e.g., archived
artifacts with no source file on disk).

## Problem
`family_id` was added to the `Strategy` schema in Churn Story 1. Nodes ingested before that
story were written without `family_id`, so they remain `null`. The correlation query in
`get_cross_artifact_correlation_v1` handles this via a fallback OR-branch:

```cypher
WHERE (anchor.family_id IS NOT NULL AND related.family_id = anchor.family_id ...)
   OR (anchor.family_id IS NULL AND related.logic_type = anchor.logic_type ...)
```

This fallback is intentional for backward compatibility, not correctness. Strategies that share
`logic_type + direction` but differ in signal logic (e.g., `ema_crossover` and `dual_tf_trend`,
both `TrendFollowing bear`) will continue to be grouped together until backfill completes.

## Goal
Populate `family_id` on all pre-existing `Strategy` nodes so the family-scoped correlation
branch is activated for the full graph.

## Approach

### Path A — Re-ingest (preferred)
For each strategy that has a source file on disk, re-run `qw record` with `--source-file`:

```bash
# Re-ingest with source file to set family_id
qw record <artifact_path> --source-file strategies/bear_es_sweep_1h_baseline.py
```

`persist_artifact` uses MERGE on `strategy_id`, so re-ingestion is idempotent. Only `family_id`
and `updated_at` change. Run stats and champion nodes are unaffected.

**Prerequisite:** The operator must verify that the source file on disk matches the version used
to produce the original runs. If the strategy has been modified since ingestion, the new
`source_hash` will be different, producing a different `family_id` than the original.

### Path B — Direct Cypher patch (fallback for archived strategies)
For strategies where the source file is no longer available at the original version, apply
`family_id` directly via Cypher using a manually-derived or preserved hash:

```cypher
MATCH (s:Strategy {strategy_id: $strategy_id})
SET
  s.family_id = $family_id,
  s.updated_at = datetime()
```

This requires the operator to supply the `family_id` value. Compute it offline:

```python
from research.graph.ids import family_id, source_hash
fid = family_id("MeanReversion", "bear", source_hash(open("strategies/rsi_reversion.py", "rb").read()))
```

### Path C — `qw backfill-family` CLI command (V2 automation)
A future `qw backfill-family` command could iterate all `Strategy` nodes with `family_id IS NULL`,
prompt the operator to supply the source file for each, and apply the patch. Out of scope for
this story; implement if Path A becomes operationally burdensome.

## Migration Query (Audit)
To identify nodes that need backfill:

```cypher
MATCH (s:Strategy)
WHERE s.family_id IS NULL
RETURN s.strategy_id, s.logic_type, s.direction, s.created_at
ORDER BY s.created_at ASC
```

## Acceptance Criteria
- [x] All `Strategy` nodes with `family_id IS NULL` identified via audit query.
      `AUDIT_NULL_FAMILY_ID_QUERY` in `research/graph/cypher.py`.
      `GraphStore.audit_null_family_ids()` returns list of null-family Strategy dicts.
- [x] Each null-`family_id` node patched via Path A or Path B.
      Path A: use existing `qw record --source-file`. Path B: `GraphStore.patch_family_id(strategy_id, family_id)`.
      Both methods verified by unit tests in `tests/unit/test_backfill.py` (14/14 passing).
- [x] Post-migration audit query returns zero rows.
      Graph was empty at migration time (2026-04-04). No pre-existing null-family_id nodes existed.
- [x] `get_cross_artifact_correlation_v1` smoke-tested.
      Graph was empty; no cross-family contamination possible. OR-branch logic verified by unit tests.
- [x] This document updated with the list of strategies patched and method used.
      No strategies required patching. Graph was empty prior to family_id schema availability.

## Definition of Done
- [x] Zero `Strategy` nodes with `family_id IS NULL` in the graph. (vacuously — graph was empty)
- [x] Correlation results verified. (vacuously — no strategies to cross-pollute)
- [x] Story marked CLOSED.

## Implementation Note
Infrastructure added in `research/graph/cypher.py` and `research/graph/store.py`:

```
AUDIT_NULL_FAMILY_ID_QUERY  — identifies Strategy nodes with family_id IS NULL
PATCH_FAMILY_ID_QUERY       — sets family_id on a single Strategy node (Path B)
GraphStore.audit_null_family_ids() → list[dict]
GraphStore.patch_family_id(strategy_id, family_id) → bool
```

Also added `qws_graph/conftest.py` — stubs pandas before neo4j imports it, fixing a
numpy/pandas binary incompatibility in the conda env that blocked collection of all
tests importing `neo4j`.

Operator runbook for **Path A** (preferred):
```bash
# For each strategy with source file on disk:
qw record <artifact_path> --source-file strategies/<strategy_file>.py

# Verify after each:
python -c "
from research.graph.store import GraphStore
s = GraphStore.from_env()
print(s.audit_null_family_ids())
"
```

Operator runbook for **Path B** (no source file available):
```python
from research.graph.ids import family_id, source_hash
from research.graph.store import GraphStore

fid = family_id("MeanReversion", "bear", source_hash(open("strategies/rsi_reversion.py", "rb").read()))
store = GraphStore.from_env()
patched = store.patch_family_id("rsi-reversion-es-1h-bear", fid)
print("patched:", patched)
```

## In Scope
- Backfill `family_id` on pre-existing `Strategy` nodes.
- Audit query to identify null nodes.
- Operator runbook for Path A re-ingest.

## Out of Scope
- `qw backfill-family` CLI automation (Path C — deferred).
- Backfill of `BlobArtifact` or `Champion` nodes (no `family_id` field on these labels).
- Schema changes — `family_id` is already in the V1 schema.

## Dependencies
- Depends on: `story_strategy_family_definitions.md` — CLOSED. `family_id` derivation spec.
- Depends on: Churn Story 1 — CLOSED. `family_id` schema and `--source-file` CLI flag.
- Enables: Full accuracy of `get_cross_artifact_correlation_v1` at scale.
