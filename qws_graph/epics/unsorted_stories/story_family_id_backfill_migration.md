# Story — family_id Backfill Migration

## Status
draft

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
- [ ] All `Strategy` nodes with `family_id IS NULL` identified via audit query.
- [ ] Each null-`family_id` node patched via Path A or Path B.
- [ ] Post-migration audit query returns zero rows.
- [ ] `get_cross_artifact_correlation_v1` smoke-tested: family-scoped OR-branch activates for
      all strategies (verify by checking `family_id` field in `CrossArtifactRowV1` output).
- [ ] This document updated with the list of strategies patched and method used.

## Definition of Done
- [ ] Zero `Strategy` nodes with `family_id IS NULL` in the graph.
- [ ] Correlation results verified: same-family strategies correlate; different-family strategies
      in the same `logic_type` bucket no longer cross-pollute.
- [ ] Story marked CLOSED.

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
