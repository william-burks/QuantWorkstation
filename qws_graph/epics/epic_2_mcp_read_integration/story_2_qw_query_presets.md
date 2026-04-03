# Story 2 — `qw query` Presets

## Status
draft

## Summary
Implement operator-focused graph query presets on top of read projections.

## Problem
Users need stable, named queries rather than ad-hoc Cypher for common tasks.

## Goal
Add contract-backed `qw query` presets for high-value retrieval paths.

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

## Out of Scope
- Free-form arbitrary Cypher execution
- Query UI/dashboard

## Repo Touchpoints
- `research/graph/cli.py`
- `research/graph/query_presets.py`
- `tests/unit/test_qw_query.py`

## Implementation Notes
- Keep preset names stable and documented.
- Validate preset parameters before query execution.

## Acceptance Criteria
- [ ] `qw query --name recent_champions` works.
- [ ] `qw query --name strategy_lineage --param strategy_id=...` works.
- [ ] Invalid preset names return deterministic error.
- [ ] `--json` output shape is stable.

## Validation
- Unit tests for preset routing and parameter validation.
- Integration checks on seeded graph test dataset.

## Definition of Done
- [ ] Preset catalog implemented with tests.
- [ ] CLI help documents available presets.

## Open Questions
- None.

## Notes
This story should remain read-only and avoid expanding write surfaces.

