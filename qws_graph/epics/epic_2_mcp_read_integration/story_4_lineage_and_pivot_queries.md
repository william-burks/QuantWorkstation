# Story 4 — Lineage and Pivot Queries

## Status
draft

## Summary
Run the Epic 2 acid test with focused lineage/pivot retrieval paths that prove real graph-ledger query value.

## Problem
The key graph value is relationship traversal; without lineage/pivot queries, users still rely on manual file tracing.

## Goal
Implement first-class lineage and cross-artifact correlation queries using explicit graph relationships (including `--pivot-from` edges).

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
- Cross-artifact correlation retrieval (for example ES vs NQ, 5m vs 1h) through shared `Strategy` anchors

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
- Implement through shared query view functions (not ad-hoc per-caller Cypher variants).
- Keep validation Neo4j-only; missing relationships should return deterministic empty/not-found results.

## Canonical Graph Semantics (Required)
- Lineage/pivot traversal uses canonical Graph V1 path `(:Strategy)-[:PRODUCED_CHAMPION]->(:Champion)-[:PIVOTED_FROM]->(:Run)` plus `(:Strategy)-[:HAS_RUN]->(:Run)`/`(:Run)-[:USES_CONFIG]->(:Config)` where needed.
- Cross-artifact correlation must anchor on shared canonical `Strategy` properties/relationships, not new persisted labels.
- Alias artifact-to-artifact wording is permitted only at response/docs layer; stored semantics remain Champion-to-Run pivot edges.

## Acceptance Criteria
- [ ] Strategy lineage query returns ordered chain.
- [ ] Pivot query returns empty list when no explicit pivot edges exist.
- [ ] Multi-hop lineage traversal is bounded and documented.
- [ ] Cross-artifact correlation query returns related runs/champions through shared `Strategy` anchors without artifact file parsing.

## Validation
- Seeded graph fixtures with known lineage graph.
- Snapshot tests for returned JSON.

## Definition of Done
- [ ] Query functions implemented and tested.
- [ ] Preset docs updated.

## Open Questions
- None.

## Notes
This is the Epic 2 acid test story: if these scenarios are not easy to answer via graph queries, read-model utility is not yet proven.

