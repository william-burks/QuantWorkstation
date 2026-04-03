# Story 1 — Graph V1 Contract Alignment

## Status
ready

## Summary
Freeze the implementation contract so all V1 graph code follows one source of truth.

## Problem
Without a single contract, model fields, IDs, CLI exit codes, and write semantics drift across modules.

## Goal
Ensure `docs/graph_v1_contract.md` is complete, internally consistent, and directly actionable for models/parsers/CLI/store/hooks.

## Inputs
- `docs/graph_v1_contract.md`
- `docs/IS_RESEARCH_SOP.md`
- `research/results/champions/*.md`
- `results/*.csv`

## Deliverable
- Finalized contract doc updates (if needed)
- Explicit implementation checklist section in the contract

## In Scope
- Validate schema sections against actual artifact formats
- Validate deterministic ID and receipt policy definitions
- Validate shell hook contract (`qw record ... || true`)

## Out of Scope
- Writing parser or CLI code
- Neo4j schema migrations

## Repo Touchpoints
- `docs/graph_v1_contract.md`
- `qws_graph/epics/epic_1_ingestion_and_index/*`

## Implementation Notes
- Contract terms override local preferences for V1.
- Keep language implementation-grade; avoid ambiguous terms like “maybe”, “typically”.
- Confirm phase boundaries and non-goals are explicit.

## Acceptance Criteria
- [ ] Contract includes exact artifact kinds for V1 ingest.
- [ ] Contract includes deterministic key algorithm and collision strategy.
- [ ] Contract includes exact `qw record` exit codes.
- [ ] Contract includes `.qws/receipts` and `.qws/pending` behavior.
- [ ] Contract includes Cypher MERGE patterns for CSV and champion ingest.

## Validation
- Manual review checklist pass against this story’s acceptance criteria.
- Spot-check contract sections against one real CSV and one champion markdown.

## Definition of Done
- [ ] Contract is implementation-ready.
- [ ] No unresolved placeholders remain in contract sections used by V1 code.
- [ ] Epic stories reference the finalized contract consistently.

## Open Questions
- None.

## Notes
This story should complete before coding starts in `research/graph/`.

