# Epic 2 — MCP Read Integration

## Objective
Expose graph-ledger data through stable read/query contracts for agent-assisted research workflows.

## Why it exists
After ingestion is stable, the next value is reliable retrieval of lineage and champion context without direct file parsing.

## Scope
- Read models and query projections from Neo4j
- `qw query` presets for operator use
- MCP read-only contract and adapter boundary
- Pivot/lineage query support

## Stories in execution order
1. `story_1_read_models_and_query_projections.md`
2. `story_2_qw_query_presets.md`
3. `story_3_mcp_read_tool_contract.md`
4. `story_4_lineage_and_pivot_queries.md`

## Dependencies
- Epic 1 complete and stable on main
- `qw record` + `qw reconcile` validated
- Graph nodes/edges populated from real artifacts

## Exit criteria
- Query surfaces can retrieve run/config/champion lineage from graph only
- MCP read contract documented and implementable
- No direct artifact parsing required by read path

