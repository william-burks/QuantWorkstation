# Story 2 — `qw query` Presets

## Status
draft

## Summary
Implement the operator-facing Bridge surface: stable `qw query` presets on top of Story 1 read projections.

## Problem
Users need stable, named queries rather than ad-hoc Cypher for common tasks.

## Goal
Add contract-backed `qw query` presets for high-value retrieval paths so CLI and MCP layers reuse the same Query API.

## Inputs
- Story 1 projection models
- `docs/graph_v1_contract.md` query section
- Existing graph data from Epic 1

## Deliverable
- `qw query` command support in `research/graph/cli.py`
- Query preset catalog in `research/graph/query_presets.py`

## In Scope
- Presets:
  - `recent_champions`
  - `strategy_lineage`
  - `pending_offline`
- JSON output mode for automation
- Clear mapping from preset names/params to `research/graph/query.py` view functions from Story 1

## Canonical Graph Semantics (Required)
- Presets route only to Story 1 views built on canonical labels/edges (`Strategy`, `Run`, `Config`, `Champion`, `BlobArtifact`; `HAS_RUN`, `USES_CONFIG`, `PRODUCED_CHAMPION`, `PIVOTED_FROM`, `HAS_BLOB`).
- Alias terms may be accepted at CLI parameter/docs level but must resolve to canonical Graph V1 semantics.
- Presets must not introduce persisted `Artifact` or `Instrument` nodes/relationships.

## Out of Scope
- Free-form arbitrary Cypher execution
- Query UI/dashboard
- Duplicating Cypher/query logic in CLI command handlers

## Repo Touchpoints
- `research/graph/cli.py`
- `research/graph/query_presets.py`
- `tests/unit/test_qw_query.py`

## Implementation Notes
- Keep preset names stable and documented.
- Validate preset parameters before query execution.
- Treat presets as name-based routing to view functions; CLI is orchestration, not query-definition.

## Acceptance Criteria
- [ ] `qw query --name recent_champions` works.
- [ ] `qw query --name strategy_lineage --param strategy_id=...` works.
- [ ] Invalid preset names return deterministic error.
- [ ] `--json` output shape is stable.
- [ ] Preset implementation calls code-defined query views by stable function name.

## Validation
- Unit tests for preset routing and parameter validation.
- Integration checks on seeded graph test dataset.

## Definition of Done
- [ ] Preset catalog implemented with tests.
- [ ] CLI help documents available presets.

## Open Questions
- None.

## Notes
This story is the CLI half of the Bridge and remains read-only with no write-surface expansion.

