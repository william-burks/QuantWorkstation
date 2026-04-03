# Story 4 — Neo4j Idempotent Store

## Status
ready

## Summary
Implement transactional, idempotent graph persistence for V1 artifacts.

## Problem
Validated payloads are not useful without stable write semantics that prevent duplicates and broken lineage.

## Goal
Provide a store layer that applies contract MERGE mappings and guarantees repeat-ingest idempotency.

## Inputs
- `docs/graph_v1_contract.md` (Cypher mappings)
- Story 2 payloads
- Story 3 CLI invocation path

## Deliverable
- `research/graph/store.py`
- Optional `research/graph/cypher.py`
- Store-level tests against Neo4j test instance

## In Scope
- Strategy/Run/Config/Champion/Blob MERGE operations
- One transaction per artifact ingest
- Deterministic PK-based relationship writes
- Basic connection and timeout handling

## Out of Scope
- Graph analytics queries
- Benchmark resolver implementation
- MCP adapters

## Repo Touchpoints
- `research/graph/store.py`
- `docker-compose.neo4j.yml` (if needed by test/dev)
- `tests/integration/test_graph_store.py`

## Implementation Notes
- Keep Cypher near contract text to reduce drift.
- Use parameterized queries only.
- Return node/relationship counts for receipt output.

## Acceptance Criteria
- [ ] Double-ingesting same artifact does not create extra nodes.
- [ ] Double-ingesting same artifact does not create extra relationships.
- [ ] Champion ingest creates `PRODUCED_CHAMPION` and optional `PIVOTED_FROM`.
- [ ] Store returns counts and status for receipts.
- [ ] Infra errors propagate as store-layer exceptions.

## Validation
- Integration tests with clean graph then repeated ingest.
- Manual check in Neo4j Browser for duplicate prevention.

## Definition of Done
- [ ] Store layer follows contract MERGE semantics.
- [ ] Idempotency tests pass.
- [ ] CLI can call store successfully for CSV and champion artifacts.

## Open Questions
- None.

## Notes
This story is the hard boundary before adding shell hooks.

