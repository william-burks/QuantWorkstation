# Story 4 — Cutover Guardrails and Rollback

## Status
draft

## Summary
Define and implement controlled cutover criteria and rollback procedures for graph-primary decision workflows.

## Problem
Graph-primary adoption without explicit rollback criteria creates operational risk for ongoing research.

## Goal
Ship a cutover playbook with objective checks and a tested rollback path.

## Inputs
- Epic 1 and Epic 2 completion metrics
- Story 1-3 outputs in this epic
- Existing shell/script workflows

## Deliverable
- `docs/graph_cutover_playbook.md`
- Optional `qw health`/`qw reconcile --strict` checks
- Rollback runbook steps

## In Scope
- Cutover readiness checklist
- Required reliability metrics (ingest success, drift rate, query reliability)
- Rollback actions to file-led workflow

## Out of Scope
- Infrastructure HA design
- Multi-environment deployment policy

## Repo Touchpoints
- `docs/graph_cutover_playbook.md`
- `research/graph/cli.py`
- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`

## Implementation Notes
- Keep rollback practical: no schema rewrites required to fall back.
- Preserve shell-first execution even after cutover.

## Acceptance Criteria
- [ ] Cutover checklist includes objective thresholds.
- [ ] Rollback plan can be executed in < 30 minutes.
- [ ] Reconcile/health commands support go/no-go checks.

## Validation
- Tabletop dry run of cutover and rollback sequence.
- Simulated Neo4j outage after cutover and successful fallback.

## Definition of Done
- [ ] Playbook authored and reviewed.
- [ ] Guardrail commands implemented.
- [ ] Rollback path tested and documented.

## Open Questions
- Who owns cutover sign-off in practice.

## Notes
Final story before declaring graph-primary decision state operational.

