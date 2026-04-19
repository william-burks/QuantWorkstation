# Story 1 — Read Models and Query Projections

## ID
# QWS-0201

## Status
CLOSED

## Summary
Build the Bridge foundation: stable graph read projections for runs, configs, champions, and lineage.

## Problem
Raw Neo4j node shapes are not a stable API surface for tools and downstream integration.

## Goal
Provide typed read DTOs and projection queries that form the internal Query API backing both `qw query` presets and MCP consumers.

## Inputs
- `docs/graph_v1_contract.md`
- Epic 1 graph schema implementation
- Existing champion and run artifacts already ingested
- `story_0_target_state_schema_mapping.md` (read-shape alignment gate)

## Canonical Graph Semantics (Required)
- Labels: `Strategy`, `Run`, `Config`, `Champion`, `BlobArtifact`.
- Edges: `HAS_RUN`, `USES_CONFIG`, `PRODUCED_CHAMPION`, `PIVOTED_FROM`, `HAS_BLOB`.
- Alias boundary: `ResearchRun` may appear in DTO/doc naming only and maps to canonical `Run`.
- No persisted `Artifact` or `Instrument` labels in Epic 2 read surfaces.

## Deliverable
- `research/graph/query_models.py`
- `research/graph/query.py` view/projection functions

## In Scope
- Target State Schema alignment for read/query shape before implementation (no write-model changes)
- Code-defined query view functions in `research/graph/query.py` for each projection surface
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
- Treat this story as the bridge-contract layer; downstream stories consume these shapes, not raw graph node payloads.
- Projection outputs should be flattened JSON-friendly dictionaries (or lists of flat objects), not raw Neo4j record maps.

## Acceptance Criteria
- [x] Target read/query schema shape is documented and aligned with `docs/graph_v1_contract.md` before projection coding begins.
- [x] Read models exist for strategy/run/champion lineage views.
- [x] Projection functions return deterministic key names.
- [x] View functions in `research/graph/query.py` are callable by stable name for Story 2/3 routing.
- [x] Tests cover missing-edge and multi-edge scenarios.

## Validation
- Query seeded graph and verify model parsing.
- Snapshot tests for JSON projection output.

## Definition of Done
- [x] Projection layer available for `qw query`.
- [x] Typed outputs documented in module docstrings.

## Open Questions
- None.

## Notes
Foundation for `qw query` presets and MCP read adapter.

