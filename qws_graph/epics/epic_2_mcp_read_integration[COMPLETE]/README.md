# Epic 2 — MCP Read Integration

## Objective
Expose graph-ledger data through stable read/query contracts for agent-assisted research workflows.

## Why it exists
After ingestion is stable, the next value is reliable retrieval of lineage and champion context without direct file parsing.

## Scope
- Bridge layer in `qw`: read models/projections + query presets over Neo4j
- MCP read-only contract and adapter boundary for agent access
- Lineage/pivot query scenarios that prove graph-ledger retrieval value

## Weight of Work (Execution Lens)
- Bridge (Stories 1-2): establish the in-CLI Query API so operators/agents use stable presets instead of raw Cypher.
- Force Multiplier (Story 3): expose the same read/query layer to MCP so assistants can retrieve graph context natively.
- Acid Test (Story 4): validate real research retrieval by exercising lineage and cross-artifact traversal.

## Implementation Guardrails
- Flattened projection outputs: read models and MCP payloads must be deterministic, JSON-friendly dictionaries (including lists of flat objects where needed for lineage/history), not raw Neo4j structures.
- Query views as code: query presets resolve to code-defined view functions in `research/graph/query.py`; CLI and MCP both call these by stable name.
- Neo4j-only reads: no CSV/Markdown/file fallback on read paths; if data is missing in graph, return a deterministic empty/not-found result or infra error.

## Pre-Story Alignment Task
0. Target State Schema Alignment (read-shape only)
   - Lock the target read/query shape before Story 1 implementation.
   - Confirm alignment with `docs/graph_v1_contract.md` (no Graph V1 write-model changes).
   - Output: `story_0_target_state_schema_mapping.md`.

## Stories in execution order
0. `story_0_target_state_schema_mapping.md` (Schema mapping gate)
1. `story_1_read_models_and_query_projections.md` (Bridge foundation)
2. `story_2_qw_query_presets.md` (Bridge operator surface)
3. `story_3_mcp_read_tool_contract.md` (MCP force multiplier)
4. `story_4_lineage_and_pivot_queries.md` (Acid-test scenarios)

## Dependencies
- Epic 1 complete and stable on main
- `qw record` + `qw reconcile` validated
- Graph nodes/edges populated from real artifacts

## Exit criteria
- Query surfaces can retrieve run/config/champion lineage from graph only
- MCP read contract documented and implementable
- No direct artifact parsing required by read path
- Cross-Artifact Correlation: Able to query relationships between different instruments or timeframes (for example ES vs NQ, 5m vs 1h) via shared `:Strategy` anchors (`:ResearchProject` only if introduced by contract revision).

> Contract note: Graph V1 currently defines `:Strategy` anchors for this correlation path; Epic 2 does not introduce new node types.

