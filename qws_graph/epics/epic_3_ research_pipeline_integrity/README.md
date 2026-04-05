# Epic 3 — Research Pipeline Integrity

## Objective
Close correctness and maintainability gaps in the trial-to-graph write path before
building graph-primary decision workflows on top of it.

## Why it exists
Epic 1 established the ingestion plumbing (`qw record`, idempotent store, shell hooks).
Epic 2 built the read surface. Both assumed the data arriving in the graph is well-formed.
This epic addresses three classes of gaps that cause silent failures or accumulating
inconsistencies in the graph:

1. **Schema gaps** — missing property keys, unresolved environment configuration, and
   incomplete end-to-end wiring for champion promotion.
2. **Duplicated schema knowledge** — strategy metadata and column mappings are hardcoded
   independently in every trial script, meaning any schema change in `qws_graph` requires
   touching every trial file.
3. **Artifact sprawl** — all trial outputs (CSV, HTML, JSON) land in a flat directory with
   no per-run isolation. Files for different runs collide; HTML reports are never linked
   to their corresponding graph `Run` node.

Epic 4 (Graph Primary Workflow) depends on clean, consistent, queryable data. This epic
is the prerequisite.

## Scope
- Wiring fixes to shell runners and the ingestion layer (env sourcing, `curator_note`
  normalization, champion promotion path).
- A shared `research/graph_export.py` utility that trial scripts call instead of managing
  schema mapping themselves.
- A standard per-run bundle directory structure and a `qw record --bundle` CLI flag to
  ingest all artifacts from a run in one command.

## Weight of Work (Execution Lens)
- **Foundation (Story 1):** Fix three concrete wiring gaps. Highest priority — blocks
  `qw query --name recent_champions` from returning clean results.
- **Correctness (Story 2):** Centralize the trial-to-graph CSV export contract. Prevents
  schema drift from propagating across trial files silently.
- **Organization (Story 3):** Co-locate per-run artifacts and add bundle ingestion. Lower
  urgency — valuable once there are multiple trial variants writing to the same directory.

## Implementation Guardrails
- No changes to `qws_graph/research/graph/parsers.py` or `models.py` schema in Stories 1-2.
  All fixes are at the call site or in new utility modules.
- `research/graph_export.py` must not import from `qws_graph` directly (avoids a cross-package
  dependency). Required fields and aliases are maintained as a static table with a test
  asserting consistency against `parsers.py`.
- Story 3 (`--bundle`) and the existing `--file` flag must be mutually exclusive in `cli.py`.
- HTML files are stored by path reference only — raw HTML content is never written to Neo4j.

## Stories in execution order
1. `story_1_graph_ingestion_schema_consistency.md` — schema and wiring fixes (P2)
2. `story_2_centralized_ingestion_layer.md` — shared CSV export utility (P2)
3. `story_3_trial_bundle_structure.md` — per-run artifact co-location and bundle ingest (P3)
4. `story_4_epic3_uat_runbook.md` — operator UAT runbook; gate before marking epic complete

## Dependencies
- Epic 1 complete and stable on main (`qw record`, idempotent store, receipts).
- Epic 2 read contracts finalized (`qw query` presets operational).
- No Epic 4 dependency — this epic is a prerequisite for Epic 4, not a dependent.

## Exit Criteria
- `qw query --name recent_champions` returns results without errors after a clean
  baseline + golden ingest from a fresh Neo4j instance.
- No trial script contains hardcoded `instrument`, `timeframe`, `direction`, or
  `logic_type` assignments or manual `n_trades` → `total_trades` mapping.
- A fresh `./research/run_liquidity_sweep_baseline.sh` without pre-exported graph env
  vars (but with a valid `qws_graph/.env`) completes with correct graph writes.
- All Run nodes have a `curator_note` property key present (value `""` when curation is off).
