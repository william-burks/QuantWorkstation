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
7. **Epic 7 — Workflow Readiness** — `COMPLETE`
8. **Epic 8 — Champion Lifecycle Hardening** — `COMPLETE`
9. **Epic 9 — Strategy Development** — `COMPLETE`
10. **Epic 9HF — Bugs & Hotfixes** — `READY` (implement now, parallel with 10)
11. **Epic 9.5 — Workflow Hardening** — `READY` (implement after 9HF)
12. **Epic 10 — Macro Data** — `PLANNED` (QWS-1012 must close before any collector closes)
13. **Epic 11 — Production Tracking** — `PLANNED`
14. **Epic 13 — Agent Design** — `PLANNED` (QWS-1301 READY; 1302-1304 blocked on gap fixes)
15. **Epic 12 — ML Research Layer** — `PLANNED`

## Dependency Notes
- Epics 1–8 COMPLETE. Epic 9 in progress — QWS-0903 READY.
- Epic 9HF: QWS-HF-001 and QWS-0904 are independent — implement in parallel.
- Epic 9.5: all 4 stories READY, no mutual deps — implement in parallel.
- Epic 10: QWS-1012 (strategy class taxonomy) must CLOSE before any collector story closes.
- Epic 12 entry blocked on QWS-0803 CLOSED (satisfied). QWS-0907 (trial_metadata) must land before QWS-1204.
- Epic 13: QWS-1301 READY; QWS-1302/1303/1304 blocked on gap fixes landing first.
- Epic 9HF stories live in `qws_graph/epics/epic_9hf_bugs_and_hotfixes/`. Future one-off hotfixes go in `qws_graph/epics/hotfix/` (currently empty).

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

## Epic 7 — Workflow Readiness [COMPLETE]
- Epic README: `epic_7_workflow_readiness[COMPLETE]/README.md`
- Objective: close gaps blocking real end-to-end research sessions

Stories (execution order — 0801 and 0703 parallel, 0804 after 0801):
1. `QWS-0801` `epic_7_workflow_readiness[COMPLETE]/closed/story_1_former_champion_lifecycle.md` — `CLOSED`
2. `QWS-0703` `epic_7_workflow_readiness[COMPLETE]/closed/story_2_openai_curation.md` — `CLOSED`
3. `QWS-0804` `epic_7_workflow_readiness[COMPLETE]/closed/story_3_correlation_gate_recheck.md` — `CLOSED`

---

## Epic 8 — Champion Lifecycle Hardening [COMPLETE]
- Epic README: `epic_8_champion_lifecycle_hardening[COMPLETE]/README.md`
- Objective: SUPERSEDED_BY direct lineage edge at promotion time; automated decay detection via scheduled validation loop

Stories (QWS-0802 and QWS-0803 independent — implement in parallel):
1. `QWS-0802` `epic_8_champion_lifecycle_hardening[COMPLETE]/closed/story_2_superseded_by_relationship.md` — `CLOSED`
2. `QWS-0803` `epic_8_champion_lifecycle_hardening[COMPLETE]/closed/story_1_recursive_validation_loop.md` — `CLOSED`
3. `QWS-0805` `epic_8_champion_lifecycle_hardening[COMPLETE]/closed/story_3_champion_promotion_rationale.md` — `CLOSED`

---

## Epic 9 — Strategy Development [COMPLETE]
- Epic README: `epic_9_strategy_development[COMPLETE]/README.md`
- Objective: use system end-to-end; document research findings, workflow friction, and tooling gaps — no code deliverables

Stories (execution order — 0901 first, 0902 after 0901, 0903 after both):
1. `QWS-0901` `epic_9_strategy_development[COMPLETE]/closed/story_1_first_research_session.md` — `CLOSED`
2. `QWS-0902` `epic_9_strategy_development[COMPLETE]/closed/story_2_strategy_screening_pass.md` — `CLOSED`
3. `QWS-0903` `epic_9_strategy_development[COMPLETE]/closed/story_3_system_gap_audit.md` — `CLOSED`

Note: this epic has no code deliverables. Done criteria = gap audit written, backlog updated.

---

## Epic 9HF — Bugs & Hotfixes [COMPLETE]
- Epic README: `epic_9hf_bugs_and_hotfixes[COMPLETE]/README.md`
- Objective: fix silent data integrity bugs discovered during Epic 9 research sessions — provenance chain breaks, phantom IDs, CLI ordering bugs

Stories (independent — implement in parallel):
- `QWS-HF-001` `epic_9hf_bugs_and_hotfixes[COMPLETE]/closed/QWS-HF-001_bundle_hypothesis_autolink.md` — `CLOSED`
- `QWS-0904` `epic_9hf_bugs_and_hotfixes[COMPLETE]/closed/QWS-0904_phantom_champion_id_fix.md` — `CLOSED`

---

## Epic 9.5 — Workflow Hardening [READY]
- Epic README: `epic_9_5_workflow_hardening/README.md`
- Objective: fix researcher friction gaps discovered during Epic 9 — hypothesis lookup, ad-hoc queries, trial metadata, CL data window

Stories (independent — implement in parallel):
- `QWS-0905` `epic_9_5_workflow_hardening/closed/story_QWS-0905_hypothesis_lookup_and_findings.md` — `CLOSED`
- `QWS-0906` `epic_9_5_workflow_hardening/closed/story_QWS-0906_adhoc_cypher_and_patch.md` — `CLOSED`
- `QWS-0907` `epic_9_5_workflow_hardening/story_QWS-0907_trial_metadata_json_blob.md` — `READY`
- `QWS-0908` `epic_9_5_workflow_hardening/story_QWS-0908_cl_historical_data_extension.md` — `READY`

---

## Epic 10 — Macro Data [PLANNED]
- Epic README: `epic_10_macro_data/README.md`
- Objective: wire macro and alternative data sources as inputs for regime signal generation

Execution order: QWS-1100a first → QWS-1000 → QWS-1001–1011 parallel (QWS-1010 parallel from start) → QWS-1100b after QWS-1100a → QWS-1100c after QWS-1100b
- `QWS-1000` `epic_10_macro_data/story_0_store_series_methods.md` — `ready`
- `QWS-1001` `epic_10_macro_data/story_cot_collector.md` — `blocked` (QWS-1000)
- `QWS-1002` `epic_10_macro_data/story_fred_macro_collector.md` — `BLOCKED` (QWS-1000)
- `QWS-1003` `epic_10_macro_data/story_eia_crude_collector.md` — `blocked` (QWS-1000)
- `QWS-1004` `epic_10_macro_data/story_baker_hughes_rig_count.md` — `blocked` (QWS-1000)
- `QWS-1005` `epic_10_macro_data/story_noaa_degree_days.md` — `blocked` (QWS-1000)
- `QWS-1006` `epic_10_macro_data/story_usda_crop_progress.md` — `blocked` (QWS-1000)
- `QWS-1007` `epic_10_macro_data/story_google_trends.md` — `blocked` (QWS-1000)
- `QWS-1008` `epic_10_macro_data/story_bdti_tanker_index.md` — `blocked` (QWS-1000)
- `QWS-1009` `epic_10_macro_data/story_economic_calendar_collector.md` — `blocked` (QWS-1000)
- `QWS-1010` `epic_10_macro_data/story_data_quality_validation.md` — `ready`
- `QWS-1011` `epic_10_macro_data/story_ndvi_crop_health_collector.md` — `blocked` (QWS-1000)
- `QWS-1012` `epic_10_macro_data/story_QWS-1012_strategy_class_taxonomy.md` — `READY` ⚠️ must close before any collector story closes
- `QWS-1100a` `epic_10_macro_data/story_prefect_1100a_scheduler_isolation.md` — `ready`
- `QWS-1100b` `epic_10_macro_data/story_prefect_1100b_flows.md` — `blocked` (QWS-1100a)
- `QWS-1100c` `epic_10_macro_data/story_prefect_1100c_daemon.md` — `blocked` (QWS-1100b)

---

## Epic 11 — Production Tracking [PLANNED]
- Epic README: `epic_11_production_tracking/README.md`
- Objective: track Champion performance in production via MLflow; split production results from research results

Stories (QWS-1101 first, QWS-1102 after):
- `QWS-1101` `epic_11_production_tracking/story_1_mlflow_champion_registration.md` — `READY`
- `QWS-1102` `epic_11_production_tracking/story_2_mlflow_oos_sync.md` — `READY`

---

---

## Epic 13 — Agent Design [PLANNED]
- Path: `epic_agent_design/`
- Objective: build research navigator, trial engineer, and research ideas layer; rewrite research-session command to orchestrate both agents
- Build order: QWS-1301 → QWS-1302 → QWS-1303 → run one manual session → QWS-1304

Stories:
- `QWS-1301` `epic_agent_design/story_QWS-1301_research_ideas_layer.md` — `READY`
- `QWS-1302` `epic_agent_design/story_QWS-1302_research_navigator_agent.md` — `CLOSED` (QWS-1301, QWS-0905, QWS-0906)
- `QWS-1303` `epic_agent_design/story_QWS-1303_trial_engineer_agent.md` — `BLOCKED` (QWS-1302, QWS-0907)
- `QWS-1304` `epic_agent_design/story_QWS-1304_research_session_command_rewrite.md` — `BLOCKED` (QWS-1302, QWS-1303)

---

## Backlog [UNSCHEDULED]
- Backlog README: `backlog/README.md`
- Stories not yet assigned to a sprint epic.

Stories (no order):
- `QWS-0701` `backlog/story_pypi_packaging.md` — `READY`
- `QWS-0702` `backlog/story_ci_graph_integrity.md` — `READY`

---

---

## Epic 12 — ML Research Layer [PLANNED]
- Epic README: [`epic_12_ml_research_layer/README.md`](epic_12_ml_research_layer/README.md)
- Objective: extend research pipeline with ML regime classification and feature-engineered
  signal generation; rule-based and ML strategies compete on identical evaluation criteria.

Stories (execution order):
1. `QWS-1201` [`story_1_walk_forward_purge_gap.md`](epic_12_ml_research_layer/story_1_walk_forward_purge_gap.md) — `READY`
2. `QWS-1202` [`story_2_hmm_regime_classifier.md`](epic_12_ml_research_layer/story_2_hmm_regime_classifier.md) — `READY`
3. `QWS-1203` [`story_3_feature_engineering_layer.md`](epic_12_ml_research_layer/story_3_feature_engineering_layer.md) — `PLANNED`
4. `QWS-1204` [`story_4_ml_walk_forward_harness.md`](epic_12_ml_research_layer/story_4_ml_walk_forward_harness.md) — `PLANNED`
5. `QWS-1205` [`story_5_lightgbm_signal_model.md`](epic_12_ml_research_layer/story_5_lightgbm_signal_model.md) — `PLANNED`
6. `QWS-1206` [`story_6_results_interpreter_agent.md`](epic_12_ml_research_layer/story_6_results_interpreter_agent.md) — `PLANNED`
7. `QWS-1207` [`story_7_hypothesis_miner_agent.md`](epic_12_ml_research_layer/story_7_hypothesis_miner_agent.md) — `PLANNED`

Dependency notes: QWS-1201 is prerequisite for all. QWS-1202 and QWS-1203 parallel after
QWS-1201. QWS-1204 blocked on QWS-1203. QWS-1205 and QWS-1206 blocked on QWS-1204.
QWS-1207 blocked on QWS-1206.

Epic entry blocked on: QWS-0803 CLOSED (decay monitor must be live before ML Champion
promotion).

---

## Current Focus
- **Epic 8 COMPLETE** — all 3 stories CLOSED.
- **Epic 9 COMPLETE** — all 3 stories CLOSED.
- **Immediate:** Epic 9HF (QWS-HF-001 + QWS-0904) — fix data integrity bugs before next research session.
- **Next parallel tracks:** Epic 9.5 (workflow hardening) + Epic 10 (macro data, start with QWS-1000).
- **After gaps land:** Epic 13 (agent design, QWS-1301 READY) → Epic 12 (ML research).

