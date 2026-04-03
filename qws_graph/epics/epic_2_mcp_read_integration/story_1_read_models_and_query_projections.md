# Story 1 — Read Models and Query Projections

## Status
draft

## Summary
Define stable graph read projections for runs, configs, champions, and lineage.

## Problem
Raw Neo4j node shapes are not a stable API surface for tools and downstream integration.

## Goal
Provide typed read DTOs and projection queries that can back both CLI and MCP consumers.

## Inputs
- `docs/graph_v1_contract.md`
- Epic 1 graph schema implementation
- Existing champion and run artifacts already ingested

## Deliverable
- `research/graph/query_models.py`
- `research/graph/query.py` projection functions

## In Scope
- Projection contracts for:
  - strategy summary
  - run history
  - champion details
  - config linkage
- Explicit null/empty behavior for missing optional edges

## Out of Scope
- MCP transport/protocol glue
- Write-side updates

## Repo Touchpoints
- `research/graph/query_models.py`
- `research/graph/query.py`
- `tests/unit/test_graph_query_models.py`

## Implementation Notes
- Keep DTOs versioned (`v1`) to avoid silent schema churn.
- Avoid exposing raw Cypher-specific internals to callers.

## Acceptance Criteria
- [ ] Read models exist for strategy/run/champion lineage views.
- [ ] Projection functions return deterministic key names.
- [ ] Tests cover missing-edge and multi-edge scenarios.

## Validation
- Query seeded graph and verify model parsing.
- Snapshot tests for JSON projection output.

## Definition of Done
- [ ] Projection layer available for `qw query`.
- [ ] Typed outputs documented in module docstrings.

## Open Questions
- None.

## Notes
Foundation for `qw query` presets and MCP read adapter.

