# Story 4 — Lineage and Pivot Queries

## Status
draft

## Summary
Add focused lineage/pivot retrieval paths for strategy evolution analysis.

## Problem
The key graph value is relationship traversal; without lineage/pivot queries, users still rely on manual file tracing.

## Goal
Implement first-class lineage queries that use explicit pivot edges from `--pivot-from`.

## Inputs
- Champion ingest behavior from Epic 1
- `--pivot-from` contract in `docs/graph_v1_contract.md`
- Query projection layer from Story 1

## Deliverable
- Query functions and preset wiring for lineage/pivot paths
- Tests covering no-pivot and multi-pivot histories

## In Scope
- Query by strategy_id to return run->champion->pivot chain
- Query by run_id to return downstream champion nodes
- Optional depth-limited traversal controls

## Out of Scope
- NLP parsing of tracker markdown pivot rationale
- Cross-asset benchmark analytics

## Repo Touchpoints
- `research/graph/query.py`
- `research/graph/query_presets.py`
- `tests/unit/test_lineage_queries.py`

## Implementation Notes
- Use explicit pivot edges only; no inferred pivots.
- Keep outputs compact and deterministic for MCP consumers.

## Acceptance Criteria
- [ ] Strategy lineage query returns ordered chain.
- [ ] Pivot query returns empty list when no explicit pivot edges exist.
- [ ] Multi-hop lineage traversal is bounded and documented.

## Validation
- Seeded graph fixtures with known lineage graph.
- Snapshot tests for returned JSON.

## Definition of Done
- [ ] Query functions implemented and tested.
- [ ] Preset docs updated.

## Open Questions
- None.

## Notes
Completes read-value core for Epic 2.

