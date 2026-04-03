# Story 3 — MCP Read Tool Contract

## Status
blocked

## Summary
Define and implement the minimal MCP read adapter contract backed by graph query presets.

## Problem
Without a stable adapter contract, MCP integration risks coupling directly to internal graph storage details.

## Goal
Provide a small read-only MCP-facing interface that consumes `qw query`/query module outputs.

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

## Acceptance Criteria
- [ ] Adapter exposes a documented function surface for read tools.
- [ ] Adapter returns deterministic JSON-compatible payloads.
- [ ] Adapter does not parse file-system artifacts directly.
- [ ] Errors include stable codes/messages for caller handling.

## Validation
- Unit tests mocking store/query responses.
- Contract tests for output shape.

## Definition of Done
- [ ] Adapter module merged with tests.
- [ ] Read contract documented in module or docs.

## Open Questions
- Exact MCP tool registry binding location in this repo.

## Notes
Blocked until read projections and query presets are stable.

