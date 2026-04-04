# Story 6 — README and Runbook Baseline for Current Graph Workflow

## Status
CLOSED

## Summary
Create a docs-only story that defines the first canonical `qws_graph` README and operator runbook from all closed Epic 1 delivery artifacts.

## Problem
Epic 1 implementation is complete, but operators and developers still need to read multiple closed stories to understand setup, ingestion behavior, online/offline operation, and troubleshooting.

## Goal
Produce two documentation deliverables that consolidate current behavior and make `qws_graph` usable as implemented today.

## Inputs
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/epics/epic_1_ingestion_and_index/closed/story_5_shell_hooks_receipts_and_reconcile.md`
- `qws_graph/epics/epic_1_ingestion_and_index/README.md`
- All files in `qws_graph/epics/epic_1_ingestion_and_index/closed/`

## Deliverable
1. `qws_graph/README.md` (project README baseline)
2. `qws_graph/docs/qws_graph_runbook.md` (operator runbook baseline)

## In Scope
- Define required sections and minimum content for the README baseline.
- Define required sections and minimum content for the runbook baseline.
- Require explicit coverage of all closed Epic 1 stories in both deliverables.
- Ensure runbook content reflects current online/offline, pending/receipt, and reconcile behavior.
- Migrate any remaining operator guidance from the deprecated Story 5 notes into `qws_graph/docs/qws_graph_runbook.md`.
- Delete the deprecated Story 5 notes file after migration and update references.

## Out of Scope
- New CLI, parser, storage, or hook features.
- Changes to ingestion contract semantics.
- Additional automation beyond currently delivered workflows.

## Repo Touchpoints
- `qws_graph/README.md`
- `qws_graph/docs/qws_graph_runbook.md`
- `qws_graph/epics/epic_1_ingestion_and_index/story_6_readme_and_runbook_basis.md`

## Closed Story Coverage (Required)
Both deliverables must reference and incorporate outputs from every closed story below.

| Closed Story | README Basis Coverage | Runbook Basis Coverage |
| --- | --- | --- |
| `closed/story_0_infra_scaffold_and_docker.md` | local Neo4j setup and environment flags | startup/shutdown checks and connectivity failure handling |
| `closed/story_1_graph_v1_contract_alignment.md` | ingestion contract overview and required fields | contract validation expectations during operations |
| `closed/story_2_pydantic_models_and_parsers.md` | parser/model responsibilities and artifact mapping | parse/validation failure symptoms and recovery actions |
| `closed/story_3_qw_record_cli.md` | `qw record` usage and key flags | command run paths, return behavior, and operator examples |
| `closed/story_4_neo4j_idempotent_store.md` | idempotent persistence model and deterministic IDs | duplicate-safe re-run expectations and verification checks |
| `closed/story_5_shell_hooks_receipts_and_reconcile.md` | shell integration design and outcomes | online/offline hook behavior and reconcile procedures |
| `closed/story_makefile_neo4j_lifecycle_1.md` | Makefile command surface for graph lifecycle | step-by-step environment lifecycle operations |
| `closed/story_shell_hook_timing_race.md` | hook timing constraints and artifact readiness assumptions | troubleshooting for post-run timing/race failures |
| `closed/story_strategy_artifact_output_paths.md` | canonical artifact naming/path rules | operator checks for missing/misnamed artifacts |

## Required README Sections (Deliverable 1)
- Purpose and boundaries of `qws_graph` in QuantWorkstation.
- Architecture overview and data flow from artifact output to graph persistence.
- Quickstart for online and offline modes.
- Command reference for `qw record`, `qw reconcile`, and Neo4j lifecycle commands.
- Artifact naming/path requirements and contract links.
- Pointers to runbook for operational troubleshooting.

## Required Runbook Sections (Deliverable 2)
- Day-0 setup and verification.
- Day-1 operation: online and offline execution paths.
- Receipt and pending queue behavior with reconciliation workflow.
- Common failures and exact operator response steps.
- Troubleshooting for timing race and artifact output path mismatches.
- Verification checklist for intended current behavior.

## Acceptance Criteria
- [x] Story defines exactly two documentation deliverables and their target file paths.
- [x] Deliverable 1 explicitly references all nine closed stories as input basis.
- [x] Deliverable 2 explicitly references all nine closed stories as input basis.
- [x] Story states that runbook procedures must describe how the graph is intended to work now.
- [x] Story remains docs-only and does not add implementation scope.
- [x] The deprecated Story 5 notes file is deleted after its operator guidance is migrated into `qws_graph/docs/qws_graph_runbook.md`.
- [x] No remaining docs reference the deleted Story 5 notes file.

## Validation
- [x] Confirm every file under `qws_graph/epics/epic_1_ingestion_and_index/closed/` appears in the coverage table.
- [x] Confirm required README and runbook sections are present in this story.
- [x] Confirm all operator guidance previously captured in the deleted Story 5 notes is now present in `qws_graph/docs/qws_graph_runbook.md`.
- [x] Confirm no remaining docs reference the deleted Story 5 notes file.

## Definition of Done
- [x] Story file merged in Epic 1 with acceptance criteria and validation checklist.
- [x] Epic 1 README story list includes Story 6 in execution order.
- [x] Story deliverables are created: `qws_graph/README.md` and `qws_graph/docs/qws_graph_runbook.md`.
- [x] The deprecated Story 5 notes file is removed from the repo and replaced by canonical guidance in `qws_graph/docs/qws_graph_runbook.md`.


