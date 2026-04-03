# Story 5 — Shell Hooks, Receipts, and Reconcile

## Status
ready

## Summary
Integrate `qw record` into existing shell workflows with soft-fail behavior and add reconcile support for ingestion visibility.

## Problem
Without shell hooks, ingestion is manual and easy to skip; without reconcile, drift is hard to detect.

## Goal
Wire post-run `qw record` hooks and provide `qw reconcile` to inspect missing/pending/drift state.

## Inputs
- `research/run_es_nq_baseline.sh`
- `research/run_es_phase2.sh`
- Story 3 (`qw record`)
- Story 4 (store + receipts)

## Deliverable
- Shell hook patch in the two run scripts
- `qw reconcile` command implementation
- Reconcile output format docs in CLI help

## In Scope
- Add `qw record ... || true` after successful artifact writes
- Ensure no existing script flags or flow changes
- Implement reconcile checks:
  - pending queue status
  - artifact vs graph presence
  - basic provenance mismatch reporting

## Out of Scope
- Automatic sync scheduling
- Dashboard/UI visualizations
- MCP integration

## Repo Touchpoints
- `research/run_es_nq_baseline.sh`
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
- [ ] Reconcile reports pending files and missing graph records.
- [ ] Reconcile returns non-zero only for command errors, not data drift findings.

## Validation
- Run scripts with Neo4j down and verify completion.
- Run scripts with Neo4j up and verify receipts + graph entries.
- Run `qw reconcile` and confirm expected output.

## Definition of Done
- [ ] Shell hooks merged and tested.
- [ ] Reconcile command implemented.
- [ ] Operator docs updated in CLI help or project docs.

## Open Questions
- None.

## Notes
Completes Epic 1 and enables stable ingestion/index operations.

