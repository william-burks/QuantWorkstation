# Story 2 — Promotion and OOS State Transitions

## Status
blocked

## Summary
Implement graph-backed transitions for champion promotion and OOS readiness based on explicit gate checks.

## Problem
Promotion/OOS decisions are currently recorded manually, creating inconsistency risk between docs and system state.

## Goal
Provide deterministic transition commands/checks that update graph decision state with auditability.

## Inputs
- Story 1 state model
- `docs/IS_RESEARCH_SOP.md`
- Champion docs in `research/results/champions/`

## Deliverable
- `research/graph/workflow.py` transition logic
- CLI entrypoints (e.g., `qw promote`, `qw oos-update`) if approved
- Transition audit logs/receipts

## In Scope
- Gate checks for promotion readiness and OOS pass/fail
- State transitions with explicit reason codes
- Immutable transition history records

## Out of Scope
- Automated strategy parameter tuning
- Live deployment orchestration

## Repo Touchpoints
- `research/graph/workflow.py`
- `research/graph/cli.py`
- `tests/integration/test_workflow_transitions.py`

## Implementation Notes
- Transition functions must be idempotent where possible.
- All transitions must record actor, timestamp, and source artifacts.

## Acceptance Criteria
- [ ] Promotion transition enforces documented gate checks.
- [ ] OOS transition updates state and records window outcomes.
- [ ] Invalid transitions fail with deterministic error codes.

## Validation
- Integration tests with seeded graph states.
- Regression tests against known SOP examples.

## Definition of Done
- [ ] Transition logic merged with tests.
- [ ] CLI/docs updated for transition operations.

## Open Questions
- Exact CLI command names for state transitions.

## Notes
Blocked until decision-state model is finalized and accepted.

