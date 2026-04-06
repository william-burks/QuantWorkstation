# Story 2 — CI Graph Integrity Gate

## ID
QWS-0702

## Status
draft

## Summary
Automate the `qa_graph_integrity.sh` checks so they run on every push without requiring
a live Neo4j instance. Regressions in `store.py`, `cli.py`, or `query.py` that corrupt
champion structure are caught before merge, not after a production ingest.

## Problem
`qa_graph_integrity.sh` runs 5 structural checks against the live graph and exits 0 only
when all pass. It is currently invoked manually. There is no automated gate that catches
regressions in the ingest/query path before they reach the graph.

The checks themselves are fast (< 5s). The blocker is Neo4j dependency in CI.

## Goal
A CI job that:
1. Spins up a Neo4j instance (Docker, or uses the existing `make neo4j-up` target).
2. Seeds it with a minimal fixture dataset (one strategy, a few runs, one champion).
3. Runs the 5 integrity checks.
4. Fails the build if any check fails.

Alternatively: convert the 5 checks into Python unit tests against a mock session, so
CI runs without Neo4j at all. Evaluate which approach is simpler given the existing test
infrastructure (the unit tests already use `FakeSession`).

## Design options

### Option A — Python unit tests (no Neo4j in CI)
Convert each `qa_graph_integrity.sh` check into a unit test in
`tests/unit/test_graph_integrity.py` using the existing `FakeSession` pattern.
No Docker required. Runs in < 1s. Cannot catch real query syntax errors.

### Option B — Docker Neo4j in CI (integration gate)
Add a GitHub Actions workflow step:
```yaml
services:
  neo4j:
    image: neo4j:5
    env:
      NEO4J_AUTH: neo4j/test_password
    ports:
      - 7687:7687
```
Seed from `tests/fixtures/`, run `qa_graph_integrity.sh` against it.
Catches real Cypher errors. Adds ~60s to CI run.

Recommendation: implement Option A first (fast, no infra), note Option B as follow-on.

## In Scope
- `tests/unit/test_graph_integrity.py` — 5 unit tests mirroring the 5 shell checks
- CI workflow step (GitHub Actions `.github/workflows/`) that runs these tests
- `Makefile` target `make test-integrity` for local invocation
- Document Option B as a follow-on in the story

## Out of Scope
- Full integration test suite against live Neo4j (that's Option B, a follow-on)
- Seeding fixtures for all 9 Epic 3 UAT phases
- Performance benchmarking

## Acceptance Criteria
- [ ] `make test-integrity` runs the 5 integrity unit tests and exits 0 on a clean codebase.
- [ ] Intentionally breaking a champion property (remove `metrics_sharpe`) causes the
  relevant test to fail.
- [ ] CI runs `make test-integrity` on every push to `feature/*` and `main`.
- [ ] CI badge or workflow status is visible in the repo.

## Definition of Done
- [ ] Unit tests implemented (5 checks).
- [ ] CI workflow step added.
- [ ] `Makefile` target documented.
- [ ] Story marked CLOSED.
