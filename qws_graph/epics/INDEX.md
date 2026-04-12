# QWS Graph Epics Index

Navigation and execution index for `qws_graph/epics`.

## Status Legend
- `draft` = planned, not implementation-ready
- `ready` = can be implemented now
- `blocked` = waiting on dependency
- `done` = completed

## Recommended Sprint Order
1. **Epic 1 — Ingestion and Index** — `COMPLETE`
2. **Epic 2 — MCP Read Integration** — `COMPLETE`
3. **Epic 3 — Research Pipeline Integrity** — `COMPLETE`
4. **Epic 4 — Workflow Utility** — `COMPLETE`
5. **Epic 5 — Context Enrichment** — `COMPLETE`
6. **Epic 6 — Research Analytics** — `COMPLETE`
7. **Epic 7 — Workflow Readiness** — `PLANNED` ← current sprint

## Dependency Notes
- Epics 1–6 COMPLETE.
- Epic 7 QWS-0801 and QWS-0703 are independent — implement in parallel.
- Epic 7 QWS-0804 blocked on QWS-0801 CLOSED (FormerChampion node required).
- Backlog QWS-0803 now READY (QWS-0801 CLOSED).

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

## Epic 3 — Research Pipeline Integrity [COMPLETE]
- Epic README: [`epic_3_research_pipeline_integrity/README.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/README.md)
- Objective: close correctness and maintainability gaps in the trial-to-graph write path.

Stories (execution order):
1. `QWS-0301` [`story_1_graph_ingestion_schema_consistency.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_1_graph_ingestion_schema_consistency.md) — `CLOSED`
2. `QWS-0302` [`story_2_champion_query_presets.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_2_champion_query_presets.md) — `CLOSED`
3. `QWS-0303` [`story_3_graph_integrity_qa.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_3_graph_integrity_qa.md) — `CLOSED`
4. `QWS-0304` [`story_4_config_run_schema_split.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_4_config_run_schema_split.md) — `CLOSED`
5. `QWS-0305` [`story_5_centralized_ingestion_layer.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_5_centralized_ingestion_layer.md) — `CLOSED`
6. `QWS-0306` [`story_6_trial_bundle_structure.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_6_trial_bundle_structure.md) — `CLOSED`
7. `QWS-0307` [`story_7_epic3_uat_runbook.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_7_epic3_uat_runbook.md) — `CLOSED`

Unplanned / patch stories (CLOSED):
- `QWS-0308C` [`story_was_best_property_semantics.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_was_best_property_semantics.md) — `CLOSED`
- `QWS-0309C` [`story_artifact_path_normalization.md`](epic_3_research_pipeline_integrity%5BCOMPLETE%5D/closed/story_artifact_path_normalization.md) — `CLOSED`

---

## Epic 4 — Workflow Utility [PLANNED]
- Epic README: [`epic_4_graph_primary_workflow/README.md`](epic_4_graph_primary_workflow/README.md)
- Objective: close the remaining gaps in the research-to-decision loop with minimal scope.

Stories (execution order):
1. `QWS-0402` [`story_1_oos_outcome_tracking.md`](epic_4_graph_primary_workflow/closed/story_1_oos_outcome_tracking.md) — `CLOSED`
2. `QWS-0407` [`story_4_significance_gate_properties.md`](epic_4_graph_primary_workflow/closed/story_4_significance_gate_properties.md) — `CLOSED`
3. `QWS-0406` [`story_3_workflow_query_presets.md`](epic_4_graph_primary_workflow/closed/story_3_workflow_query_presets.md) — `CLOSED`
4. `QWS-0405` [`story_2_promotion_alerts.md`](epic_4_graph_primary_workflow/closed/story_2_promotion_alerts.md) — `CLOSED`
5. `QWS-0408` [`story_5_research_target_node.md`](epic_4_graph_primary_workflow/closed/story_5_research_target_node.md) — `CLOSED`

Cancelled (preserved in `cancelled_stories/`):
- `QWS-0401` — Decision-State Model (graph schema is already the state model)
- `QWS-0403` — Graph-to-File Exports (inverts canonical flow; two-masters problem)
- `QWS-0404` — Cutover Guardrails (corporate IT concept; not applicable here)

---

---

## Epic 5 — Context Enrichment [PLANNED]
- Epic README: [`epic_5_context_enrichment/README.md`](epic_5_context_enrichment%5BCOMPLETE%5D/README.md)
- Objective: add family identity and regime context to unlock comparative queries.

Stories (execution order):
0. `QWS-0402C` [`story_0_oos_sharpe_amendment.md`](epic_5_context_enrichment%5BCOMPLETE%5D/closed/story_0_oos_sharpe_amendment.md) — `CLOSED` _(patch: amends QWS-0402; prerequisite for QWS-0503 oos_sharpe column)_
1. `QWS-0501` [`story_1_family_id_population.md`](epic_5_context_enrichment%5BCOMPLETE%5D/closed/story_1_family_id_population.md) — `CLOSED`
2. `QWS-0502` [`story_2_regime_tagging.md`](epic_5_context_enrichment%5BCOMPLETE%5D/closed/story_2_regime_tagging.md) — `CLOSED`
3. `QWS-0503` [`story_3_cross_instrument_aggregator.md`](epic_5_context_enrichment%5BCOMPLETE%5D/closed/story_3_cross_instrument_aggregator.md) — `CLOSED`
4. `QWS-0504` [`story_4_recursive_lineage_traversal.md`](epic_5_context_enrichment%5BCOMPLETE%5D/closed/story_4_recursive_lineage_traversal.md) — `CLOSED`

---

## Epic 6 — Research Analytics [COMPLETE]
- Epic README: [`epic_6_research_analytics[COMPLETE]/README.md`](epic_6_research_analytics%5BCOMPLETE%5D/README.md)
- Objective: compute research insights from graph data; Python does the math, graph provides the index.

Stories (recommended execution order: 0602 ∥ 0603 in parallel → 0601 → 0604):
1. `QWS-0602` [`closed/story_2_parameter_stability.md`](epic_6_research_analytics%5BCOMPLETE%5D/closed/story_2_parameter_stability.md) — `CLOSED`
2. `QWS-0603` [`closed/story_3_portfolio_correlation.md`](epic_6_research_analytics%5BCOMPLETE%5D/closed/story_3_portfolio_correlation.md) — `CLOSED`
3. `QWS-0601` [`story_1_hypothesis_journaling.md`](epic_6_research_analytics%5BCOMPLETE%5D/closed/story_1_hypothesis_journaling.md) — `CLOSED`
4. `QWS-0604` [`closed/story_4_semantic_hypothesis_deduplication.md`](epic_6_research_analytics%5BCOMPLETE%5D/closed/story_4_semantic_hypothesis_deduplication.md) — `CLOSED`

Dependency notes: QWS-0602 and QWS-0603 are independent — start parallel. QWS-0604 blocked on QWS-0601.

---

## Epic 7 — Workflow Readiness [PLANNED] ← current sprint
- Epic README: `epic_7_workflow_readiness/README.md`
- Objective: close gaps blocking real end-to-end research sessions

Stories (execution order — 0801 and 0703 parallel, 0804 after 0801):
1. `QWS-0801` `closed/story_1_former_champion_lifecycle.md` — `CLOSED`
2. `QWS-0703` `story_2_openai_curation.md` — `READY`
3. `QWS-0804` `story_3_correlation_gate_recheck.md` — `READY` _(unblocked by QWS-0801 CLOSED)_

---

## Backlog [UNSCHEDULED]
- Backlog README: `backlog/README.md`
- Stories not yet assigned to a sprint epic. Revisit after Epic 7 complete.

Stories (no order):
- `QWS-0701` `story_pypi_packaging.md` — `READY`
- `QWS-0702` `story_ci_graph_integrity.md` — `READY`
- `QWS-0802` `story_superseded_by_relationship.md` — `READY`
- `QWS-0803` `story_recursive_validation_loop.md` — `READY` _(unblocked by QWS-0801 CLOSED)_

---

## Current Focus
- **Epic 6 COMPLETE** — all 4 stories CLOSED.
- **Current sprint: Epic 7 Workflow Readiness**
  - QWS-0801 (FormerChampion Lifecycle) — TESTING
  - QWS-0703 (OpenAI Curation Switch) — READY, parallel with QWS-0801
  - QWS-0804 (Correlation Gate Re-check) — BLOCKED on QWS-0801

