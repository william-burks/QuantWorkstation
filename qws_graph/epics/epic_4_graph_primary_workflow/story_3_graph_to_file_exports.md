# Story 3 — Graph-to-File Exports

## ID
# QWS-0403

## Status
draft

## Summary
Generate canonical markdown/JSON exports from graph decision state for audit and continuity.

## Problem
If graph becomes decision authority, file outputs must still be reproducible for operational continuity and review.

## Goal
Create export paths that regenerate champion/registry outputs from graph state.

## Inputs
- Decision-state and lineage graph from Stories 1-2
- Existing output formats:
  - `research/results/champions/*.md`
  - `research/results/registry.json`

## Deliverable
- `research/graph/export.py`
- Export CLI commands (e.g., `qw export champion`, `qw export registry`)
- Format parity tests

## In Scope
- Export templates matching current repository style
- Deterministic ordering/formatting for diffability
- Minimal metadata headers indicating graph-generated outputs

## Out of Scope
- Rich narrative report generation
- Notebook or dashboard exports

## Repo Touchpoints
- `research/graph/export.py`
- `research/results/champions/`
- `research/results/registry.json`
- `tests/unit/test_graph_exports.py`

## Implementation Notes
- Keep exports conservative; match existing field names where feasible.
- Preserve manual editability for transition period.

## Acceptance Criteria
- [ ] Champion markdown export matches required sections.
- [ ] Registry export retains expected keys/state values.
- [ ] Export output is deterministic across repeated runs.

## Validation
- Golden-file tests comparing exported output to expected templates.
- Manual diff against current champion and registry examples.

## Definition of Done
- [ ] Export module and tests merged.
- [ ] Export commands documented.

## Open Questions
- None.

## Notes
Critical for safe rollback and auditability during cutover.

