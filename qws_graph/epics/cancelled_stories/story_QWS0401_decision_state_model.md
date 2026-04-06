# Story 1 — Decision-State Model

## ID
# QWS-0401

## Status
draft

## Summary
Define graph-native decision-state entities for promotion/OOS readiness while preserving artifact provenance.

## Problem
Current decision state is distributed across markdown docs and registry JSON, which is hard to query consistently.

## Goal
Introduce explicit graph state model for strategy lifecycle decisions.

## Inputs
- `docs/IS_RESEARCH_SOP.md`
- `research/results/registry.json`
- `docs/graph_v1_contract.md`

## Deliverable
- Decision-state model spec and implementation module (likely `research/graph/workflow_models.py`)
- Migration mapping from existing registry statuses

## In Scope
- State enums for IS/OOS/promotion outcomes
- Edge model linking Strategy, Run, Champion, OOS windows
- Provenance links to source artifacts

## Out of Scope
- Live trading state machine
- Broker execution integration

## Repo Touchpoints
- `research/graph/workflow_models.py`
- `research/results/registry.json`
- `tests/unit/test_workflow_models.py`

## Implementation Notes
- Keep state machine finite and explicit.
- Preserve backward readability by mapping legacy statuses.

## Acceptance Criteria
- [ ] State model covers phase progression used in SOP.
- [ ] Each transition has preconditions and resulting state.
- [ ] Model can represent rejected/archived paths.

## Validation
- Unit tests for legal and illegal transitions.
- Sample conversion from existing registry entry to model.

## Definition of Done
- [ ] State model implemented and tested.
- [ ] Transition table documented.

## Open Questions
- None.

## Notes
This is prerequisite for graph-primary decision operations.

