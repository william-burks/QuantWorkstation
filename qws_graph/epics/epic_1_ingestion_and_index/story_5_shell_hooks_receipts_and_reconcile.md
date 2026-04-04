# Story 5 — Shell Hooks and Receipt Operations

## Status
CLOSED

## Summary
Integrate `qw record` into existing shell workflows with soft-fail behavior and verify receipt/pending operations in live script paths.

## Problem
Without shell hooks, ingestion is manual and easy to skip; receipt/pending behavior also goes unverified in real execution paths.

## Goal
Wire post-run `qw record` hooks and validate end-to-end script behavior under online/offline graph conditions.

## Inputs
- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`
- Story 3 (`qw record`)
- Story 4 (store + receipts)

## Deliverable
- Shell hook patch in the two run scripts
- Receipt/pending behavior verification notes
- Shell-level runbook notes for warning/retry/offline fallback

## In Scope
- Add `qw record ... || true` after successful artifact writes
- Ensure no existing script flags or flow changes
- Verify receipt/pending outcomes for online and offline runs

## Out of Scope
- Automatic sync scheduling
- Dashboard/UI visualizations
- MCP integration

## Repo Touchpoints
- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`
- `research/graph/cli.py`
- `.qws/receipts/`
- `.qws/pending/`

## Implementation Notes
- Hooks should log warnings but must not break research execution.
- Keep shell snippets readable and explicit for manual operators.
- Reconcile output should support both human and JSON formats.

## Acceptance Criteria
- [ ] Hooks execute `qw record` in both run scripts.
- [ ] Hook failures do not stop script execution.
- [ ] Online run writes receipts to `.qws/receipts/`.
- [ ] Offline run writes pending payloads to `.qws/pending/`.

## Validation
- Run scripts with Neo4j down and verify completion.
- Run scripts with Neo4j up and verify receipts + graph entries.
- Verify warning/retry messaging is visible when handshake fails.

## Definition of Done
- [ ] Shell hooks merged and tested.
- [ ] Receipt/pending behavior verified in script paths.
- [ ] Operator notes updated for online/offline hook behavior.

## Open Questions
- None.

## Notes
Completes Epic 1 and enables stable ingestion/index operations.


