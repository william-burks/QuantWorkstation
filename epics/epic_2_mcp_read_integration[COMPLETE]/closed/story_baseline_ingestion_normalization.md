# Story — Baseline Ingestion Normalization

## ID
## QWS-0206C

## Status
CLOSED

## Priority
P2 — Research Integrity. Baselines are the reference floor for alpha comparison. The two
current baseline nodes (`es-1h-bear-baseline`, `nq-1h-bear-baseline`) have two confirmed issues
that will cause silent query failures as the graph grows.

## Current State (confirmed from live graph, 2026-04-05)

| Node | family_id | logic_type | sharpe | total_r |
|---|---|---|---|---|
| `es-1h-bear-baseline` | **null** | `baseline` | 0.004 | 0.051 |
| `nq-1h-bear-baseline` | **null** | `baseline` | -0.550 | -9.369 |

Both Strategy nodes are missing `family_id`. Both use `logic_type = "baseline"`, which is
**not a canonical taxonomy value**. The canonical values are `MeanReversion`, `TrendFollowing`,
`Momentum`, `Sweep`.

Config node `db074dc6ef13` is correct — `params_json` contains strategy parameters and
`risk_params` contains risk parameters, not performance data. No Config/Run collision exists.

## Problem

### Issue 1 — Missing family_id
Both baseline Strategy nodes have `family_id = null`. The family-scoped branch of
`get_cross_artifact_correlation_v1` will never activate for these nodes. They fall back to the
`logic_type + direction` axis, which groups them with any other `logic_type = "baseline"` bear
strategies — a bucket that will stay small and low-value.

### Issue 2 — Non-canonical logic_type
The non-canonical value comes from the generated CSV payload. The baseline strategy scripts call
`build_baseline_summary_for_csv(...)` without a `logic_type` override, and that helper defaulted
to `baseline`. `CSVParser._resolve_strategy` prioritizes the CSV `logic_type` column when present,
so filename inference never corrected it.

With `logic_type = "baseline"`, the cross-artifact fallback query (`logic_type = anchor.logic_type`)
will never correlate these nodes with actual sweep strategies. The baseline's purpose is to be
the floor reference for sweep strategy comparison — but the current label severs that relationship.

## Goal
Re-ingest both baseline artifacts with the correct `logic_type` and `--source-file` so that:
1. `family_id` is set deterministically from source file bytes.
2. If both scripts are structurally identical, baselines share the same `family_id`; otherwise,
   each baseline gets a deterministic (non-null) `family_id` from its own source bytes.
3. `logic_type` is corrected to `Sweep` in the ingestion output.

## Approach

### Step 1 — Confirm source file content
The two scripts are in `strategies/`:

```zsh
diff strategies/bear_es_sweep_1h_baseline.py \
     strategies/bear_nq_sweep_1h_baseline.py
```

- If they differ only by instrument string → same logic, different params → they SHOULD share
  a `family_id`. The correct approach is to use a single canonical source file for the hash,
  or strip instrument-specific lines before hashing.
- If they have structural differences → different logic → different `family_id` is correct.

Implementation result: scripts are not identical (structural differences beyond ticker), so
different `family_id` values are expected and correct.

### Step 2 — Fix logic_type at the source
The `logic_type = "baseline"` value comes from either:
a. The CSV content (a column the parser reads), OR
b. The parser inferring from the filename.

Investigate which and correct to `Sweep`. If the CSV contains the value, fix the script. If
the parser infers it, update the parser's filename-to-logic_type mapping.

### Step 3 — Delete and re-ingest
Once Step 2 is confirmed, delete the current nodes and re-ingest:

```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)-[:USES_CONFIG]->(c:Config)
WHERE s.strategy_id IN ['es-1h-bear-baseline', 'nq-1h-bear-baseline']
DETACH DELETE s, r, c
```

Then re-ingest with `--source-file`:

```zsh
qw record \
  --file results/es_bear_sweep_1h_baseline.csv \
  --kind baseline_csv \
  --source-file strategies/bear_es_sweep_1h_baseline.py

qw record \
  --file results/nq_bear_sweep_1h_baseline.csv \
  --kind baseline_csv \
  --source-file strategies/bear_nq_sweep_1h_baseline.py
```

### Step 4 — Verify
```cypher
MATCH (s:Strategy)
WHERE s.strategy_id IN ['es-1h-bear-sweep', 'nq-1h-bear-sweep']
RETURN s.strategy_id, s.logic_type, s.family_id
```

Expected:
- `logic_type = "Sweep"` on both
- `family_id` is non-null on both
- If the scripts are structurally identical, both share the same `family_id`

## Acceptance Criteria
- [x] `logic_type` source confirmed: CSV column or parser inference. Root cause documented here.
- [x] `logic_type` corrected to `Sweep` in the ingestion output for both baselines.
- [x] Both Strategy nodes have non-null `family_id` after re-ingest.
- [x] `audit_null_family_ids()` returns zero rows.
- [x] If ES and NQ scripts are same logic: both share identical `family_id`.
- [x] `qw query --run-history --param strategy_id=es-1h-bear-sweep --json` returns a valid row.

## Out of Scope
- Semantic annotation of baseline runs (`curator_note`). Baselines are fixed reference points,
  not grid-sweep candidates. The analyst tier is not appropriate here.
- Parser changes beyond fixing `logic_type` inference.
- Config node schema changes (Config nodes are correct as-is).

## Definition of Done
- [x] Both baselines in graph with `logic_type = "Sweep"` and non-null `family_id`.
- [x] Root cause of `logic_type = "baseline"` documented and fixed.
- [x] Story marked CLOSED.

## Implementation Notes (2026-04-04)

- Root cause confirmed: CSV `logic_type` field was emitted as `baseline` by baseline scripts, not inferred from filename.
- Source fix applied: both baseline scripts now pass `logic_type='sweep'` into `build_baseline_summary_for_csv(...)`.
- Shell hook fix applied: `research/run_es_nq_bear_sweep_1h_baseline.sh` now passes `--source-file` for ES/NQ baseline ingests.
- Re-ingest completed with source binding:
  - `qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/bear_es_sweep_1h_baseline.py`
  - `qw record --file results/nq_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/bear_nq_sweep_1h_baseline.py`
- Graph verification:
  - `es-1h-bear-sweep`: `logic_type=sweep`, `family_id=2248905f1b5a`
  - `nq-1h-bear-sweep`: `logic_type=sweep`, `family_id=7305f90925f6`
- `audit_null_family_ids()` result: `count=0`.
- `qw query --run-history --param strategy_id=es-1h-bear-sweep --json` returned a valid run row (`run_id=b02686836c46`).

## Dependencies
- Depends on: Churn Story 1 (`family_id` schema) — CLOSED.
- Depends on: `story_family_id_backfill_migration.md` — CLOSED (tooling available).
- Blocks: `get_cross_artifact_correlation_v1` returning baselines in family-scoped clusters.
