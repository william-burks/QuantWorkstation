# Story 3 — MCP Read Tool Contract

## Status
CLOSED

## Summary
Implement the MCP force-multiplier layer: a minimal read adapter contract backed by the Bridge query presets.

## Problem
Without a stable adapter contract, MCP integration risks coupling directly to internal graph storage details.

## Goal
Provide a small read-only MCP-facing interface that exposes Story 1/2 query outputs to agents without introducing new query semantics.

## Inputs
- Story 1 and Story 2 outputs
- `docs/graph_v1_contract.md` MCP read contract

## Deliverable
- `research/graph/mcp_adapter.py` (or equivalent module)
- Read contract documentation for tool inputs/outputs/errors

## In Scope
- Read-only calls for:
  - recent champions
  - strategy lineage
  - run/champion context neighborhood
- Standardized error envelope
- Reuse of existing query projection/preset contracts instead of MCP-specific graph traversal logic
- Name-based binding from MCP tools to `research/graph/query.py` view functions

## Canonical Graph Semantics (Required)
- Adapter reads through Story 1/2 query views that use canonical Graph V1 labels/edges (`Strategy`, `Run`, `Config`, `Champion`, `BlobArtifact`; `HAS_RUN`, `USES_CONFIG`, `PRODUCED_CHAMPION`, `PIVOTED_FROM`, `HAS_BLOB`).
- Alias terms exposed to MCP callers are translation-only and cannot change underlying graph semantics.
- No MCP read path may imply persisted `Artifact`/`Instrument` nodes not present in Graph V1.

## Out of Scope
- MCP write APIs
- Browser ingestion bridge
- Tooling/UI integrations

## Repo Touchpoints
- `research/graph/mcp_adapter.py`
- `research/graph/query.py`
- `research/graph/query_presets.py`
- `tests/unit/test_mcp_adapter.py`

## Implementation Notes
- Adapter should depend on projection layer, not raw Cypher strings.
- Enforce Neo4j-only read policy from contract.
- MCP payloads should be flattened, deterministic JSON dictionaries (including list-of-object collections where needed).

## Acceptance Criteria
- [x] Adapter exposes a documented function surface for read tools.
- [x] Adapter returns deterministic JSON-compatible payloads.
- [x] Adapter does not parse file-system artifacts directly.
- [x] Errors include stable codes/messages for caller handling.
- [x] Missing graph data never triggers file fallback; adapter returns deterministic empty/not-found or infra error response.

## Validation
- Unit tests mocking store/query responses.
- Contract tests for output shape.

## Definition of Done
- [x] Adapter module merged with tests.
- [x] Read contract documented in module or docs.

## Open Questions
- Exact MCP tool registry binding location in this repo.

## Notes
Blocked until read projections and query presets are stable.

