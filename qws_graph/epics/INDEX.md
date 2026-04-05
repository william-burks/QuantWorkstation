# QWS Graph Epics Index

Navigation and execution index for `qws_graph/epics`.

## Status Legend
- `draft` = planned, not implementation-ready
- `ready` = can be implemented now
- `blocked` = waiting on dependency
- `done` = completed

## Recommended Sprint Order
1. **Epic 1 — Ingestion and Index** (`epic_1_ingestion_and_index/`) — `COMPLETE`
2. **Epic 2 — MCP Read Integration** (`epic_2_mcp_read_integration/`) — `COMPLETE`
3. **Epic 3 — Research Pipeline Integrity** (`epic_3_ research_pipeline_integrity/`)
4. **Epic 4 — Graph Primary Workflow** (`epic_4_graph_primary_workflow/`)

## Dependency Notes
- Epic 2 starts after Epic 1 is stable on main (`qw record` + idempotent store + reconcile working).
- Epic 3 starts after Epic 2 read contracts are stable and query projections are finalized.
- Epic 4 starts after Epic 3 exit criteria are met — graph-primary decisions depend on clean, consistent data.
- Graph-primary cutover requires explicit rollback playbook and guardrail checks.

---

## Epic 1 — Ingestion and Index [COMPLETE]
- Epic README: [`epic_1_ingestion_and_index/README.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/README.md)
- Objective: sidecar ingestion/index without breaking current shell/script entrypoints.

Stories (execution order):
- `QWS-0100` [`story_0_infra_scaffold_and_docker.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_0_infra_scaffold_and_docker.md) — `CLOSED`
- `QWS-0101` [`story_1_graph_v1_contract_alignment.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_1_graph_v1_contract_alignment.md) — `CLOSED`
- `QWS-0102` [`story_2_pydantic_models_and_parsers.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_2_pydantic_models_and_parsers.md) — `CLOSED`
- `QWS-0103` [`story_3_qw_record_cli.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_3_qw_record_cli.md) — `CLOSED`
- `QWS-0104` [`story_4_neo4j_idempotent_store.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_4_neo4j_idempotent_store.md) — `CLOSED`
- `QWS-0105` [`story_5_shell_hooks_receipts_and_reconcile.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_5_shell_hooks_receipts_and_reconcile.md) — `CLOSED`
- `QWS-0106` [`story_6_readme_and_runbook_basis.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_6_readme_and_runbook_basis.md) — `CLOSED`

Unplanned / patch stories (CLOSED):
- `QWS-0107C` [`story_baseline_csv_validation_regression.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_baseline_csv_validation_regression.md) — `CLOSED`
- `QWS-0108C` [`story_makefile_neo4j_lifecycle_1.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_makefile_neo4j_lifecycle_1.md) — `CLOSED`
- `QWS-0109C` [`story_shell_hook_timing_race.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_shell_hook_timing_race.md) — `CLOSED`
- `QWS-0110C` [`story_strategy_artifact_output_paths.md`](epic_1_ingestion_and_index%5BCOMPLETE%5D/closed/story_strategy_artifact_output_paths.md) — `CLOSED`

---

## Epic 2 — MCP Read Integration [COMPLETE]
- Epic README: [`epic_2_mcp_read_integration/README.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/README.md)
- Objective: stable graph read/query surfaces for agent-assisted research retrieval.

Stories (execution order):
- `QWS-0200` [`story_0_target_state_schema_mapping.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_0_target_state_schema_mapping.md) — `CLOSED`
- `QWS-0201` [`story_1_read_models_and_query_projections.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_1_read_models_and_query_projections.md) — `CLOSED`
- `QWS-0202` [`story_2_qw_query_presets.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_2_qw_query_presets.md) — `CLOSED`
- `QWS-0203` [`story_3_mcp_read_tool_contract.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_3_mcp_read_tool_contract.md) — `CLOSED`
- `QWS-0204` [`story_4_lineage_and_pivot_queries.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_4_lineage_and_pivot_queries.md) — `CLOSED`

Unplanned / patch stories (CLOSED):
- `QWS-0205C` [`spike_lean_neighborhood_optimization.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/spike_lean_neighborhood_optimization.md) — `CLOSED`
- `QWS-0206C` [`story_baseline_ingestion_normalization.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_baseline_ingestion_normalization.md) — `CLOSED`
- `QWS-0207C` [`story_cross_instrument_family_validation.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_cross_instrument_family_validation.md) — `CLOSED`
- `QWS-0208C` [`story_docs_sync_epic2.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_docs_sync_epic2.md) — `CLOSED`
- `QWS-0209C` [`story_family_definitions_significance_filtering.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_family_definitions_significance_filtering.md) — `CLOSED`
- `QWS-0210C` [`story_family_id_backfill_migration.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_family_id_backfill_migration.md) — `CLOSED`
- `QWS-0211C` [`story_semantic_gate_llama4.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_semantic_gate_llama4.md) — `CLOSED`
- `QWS-0212C` [`story_strategy_family_definitions.md`](epic_2_mcp_read_integration%5BCOMPLETE%5D/closed/story_strategy_family_definitions.md) — `CLOSED`

---

## Epic 3 — Research Pipeline Integrity [PLANNED]
- Epic README: [`epic_3_ research_pipeline_integrity/README.md`](epic_3_%20research_pipeline_integrity/README.md)
- Objective: close correctness and maintainability gaps in the trial-to-graph write path.

Stories (execution order):
1. `QWS-0301` [`story_1_graph_ingestion_schema_consistency.md`](epic_3_%20research_pipeline_integrity/story_1_graph_ingestion_schema_consistency.md) — `CLOSED`
2. `QWS-0302` [`story_2_config_run_schema_split.md`](epic_3_%20research_pipeline_integrity/story_2_config_run_schema_split.md) — `draft`
3. `QWS-0303` [`story_3_centralized_ingestion_layer.md`](epic_3_%20research_pipeline_integrity/story_3_centralized_ingestion_layer.md) — `draft`
4. `QWS-0304` [`story_4_trial_bundle_structure.md`](epic_3_%20research_pipeline_integrity/story_4_trial_bundle_structure.md) — `draft`
5. `QWS-0305` [`story_5_epic3_uat_runbook.md`](epic_3_%20research_pipeline_integrity/story_5_epic3_uat_runbook.md) — `draft`

---

## Epic 4 — Graph Primary Workflow [PLANNED]
- Epic README: [`epic_4_graph_primary_workflow/README.md`](epic_4_graph_primary_workflow/README.md)
- Objective: controlled shift to graph-primary decision workflows with rollback safety.

Stories (execution order):
1. `QWS-0401` [`story_1_decision_state_model.md`](epic_4_graph_primary_workflow/story_1_decision_state_model.md) — `draft`
2. `QWS-0402` [`story_2_promotion_and_oos_state_transitions.md`](epic_4_graph_primary_workflow/story_2_promotion_and_oos_state_transitions.md) — `blocked`
3. `QWS-0403` [`story_3_graph_to_file_exports.md`](epic_4_graph_primary_workflow/story_3_graph_to_file_exports.md) — `draft`
4. `QWS-0404` [`story_4_cutover_guardrails_and_rollback.md`](epic_4_graph_primary_workflow/story_4_cutover_guardrails_and_rollback.md) — `draft`
5. `QWS-0405` [`story_5_algorithmic_promotion.md`](epic_4_graph_primary_workflow/story_5_algorithmic_promotion.md) — `draft`

---

## Current Focus Suggestion
- Epic 3 Story 1 (QWS-0301, schema consistency) is CLOSED.
- Story 2 (QWS-0302, Config/Run schema split) is the current unblock — schema must be clean before the centralized layer is built on top of it.
- Story 3 (QWS-0303, centralized ingestion layer) before adding any new trial families.
- Do not begin Epic 4 work until Epic 3 exit criteria are met.

