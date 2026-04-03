# QWS Graph Epics Index

Navigation and execution index for `qws_graph/epics`.

## Status Legend
- `draft` = planned, not implementation-ready
- `ready` = can be implemented now
- `blocked` = waiting on dependency
- `done` = completed

## Recommended Sprint Order
1. **Epic 1 — Ingestion and Index** (`epic_1_ingestion_and_index/`)
2. **Epic 2 — MCP Read Integration** (`epic_2_mcp_read_integration/`)
3. **Epic 3 — Graph Primary Workflow** (`epic_3_graph_primary_workflow/`)

## Dependency Notes
- Epic 2 starts after Epic 1 is stable on main (`qw record` + idempotent store + reconcile working).
- Epic 3 starts after Epic 2 read contracts are stable and query projections are finalized.
- Graph-primary cutover requires explicit rollback playbook and guardrail checks.

---

## Epic 1 — Ingestion and Index
- Epic README: [`epic_1_ingestion_and_index/README.md`](epic_1_ingestion_and_index/README.md)
- Objective: sidecar ingestion/index without breaking current shell/script entrypoints.

Stories (execution order):
1. [`story_0_infra_scaffold_and_docker.md`](epic_1_ingestion_and_index/closed/story_0_infra_scaffold_and_docker.md) — `ready`
2. [`story_1_graph_v1_contract_alignment.md`](epic_1_ingestion_and_index/story_1_graph_v1_contract_alignment.md) — `ready`
3. [`story_2_pydantic_models_and_parsers.md`](epic_1_ingestion_and_index/story_2_pydantic_models_and_parsers.md) — `ready`
4. [`story_3_qw_record_cli.md`](epic_1_ingestion_and_index/story_3_qw_record_cli.md) — `ready`
5. [`story_4_neo4j_idempotent_store.md`](epic_1_ingestion_and_index/story_4_neo4j_idempotent_store.md) — `ready`
6. [`story_5_shell_hooks_receipts_and_reconcile.md`](epic_1_ingestion_and_index/story_5_shell_hooks_receipts_and_reconcile.md) — `ready`

---

## Epic 2 — MCP Read Integration
- Epic README: [`epic_2_mcp_read_integration/README.md`](epic_2_mcp_read_integration/README.md)
- Objective: stable graph read/query surfaces for agent-assisted research retrieval.

Stories (execution order):
1. [`story_1_read_models_and_query_projections.md`](epic_2_mcp_read_integration/story_1_read_models_and_query_projections.md) — `draft`
2. [`story_2_qw_query_presets.md`](epic_2_mcp_read_integration/story_2_qw_query_presets.md) — `draft`
3. [`story_3_mcp_read_tool_contract.md`](epic_2_mcp_read_integration/story_3_mcp_read_tool_contract.md) — `blocked`
4. [`story_4_lineage_and_pivot_queries.md`](epic_2_mcp_read_integration/story_4_lineage_and_pivot_queries.md) — `draft`

---

## Epic 3 — Graph Primary Workflow
- Epic README: [`epic_3_graph_primary_workflow/README.md`](epic_3_graph_primary_workflow/README.md)
- Objective: controlled shift to graph-primary decision workflows with rollback safety.

Stories (execution order):
1. [`story_1_decision_state_model.md`](epic_3_graph_primary_workflow/story_1_decision_state_model.md) — `draft`
2. [`story_2_promotion_and_oos_state_transitions.md`](epic_3_graph_primary_workflow/story_2_promotion_and_oos_state_transitions.md) — `blocked`
3. [`story_3_graph_to_file_exports.md`](epic_3_graph_primary_workflow/story_3_graph_to_file_exports.md) — `draft`
4. [`story_4_cutover_guardrails_and_rollback.md`](epic_3_graph_primary_workflow/story_4_cutover_guardrails_and_rollback.md) — `draft`

---

## Current Focus Suggestion
- Start with Epic 1 Story 0, then Story 1 and Story 2 in sequence.
- Implement `qw record` and `qw reconcile` in the same Story 3 PR with separate commits.
- Do not begin MCP adapter work before Epic 1 exit criteria are met.
- Keep shell-first execution behavior unchanged through Epic 1 and Epic 2.

