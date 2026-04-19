# Story 2 — CI Graph Integrity Gate

## ID
QWS-0702

## Status
READY

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
A CI job that runs the 5 integrity checks on every push without requiring a live Neo4j
instance. Converts the shell checks into Python unit tests using the existing `FakeSession`
pattern, so CI runs with no Docker dependency.

## Design

Decision: Option A (FakeSession unit tests). Option B (Docker Neo4j integration gate)
deferred as follow-on.

Convert each `qa_graph_integrity.sh` check into a unit test in
`tests/unit/test_graph_integrity.py` using the existing `FakeSession` pattern.
No Docker required. Runs in < 1s.

## Implementation Notes

- The 5 shell checks in `qa_graph_integrity.sh` use the `trace_champion` preset, which
  is deprecated and removed (per QWS-0406). The unit tests must NOT rely on the
  `trace_champion` preset. Each test should use the documented replacement
  (`downstream_champions`) or direct Cypher/Python assertions as appropriate.
- Do NOT update `qa_graph_integrity.sh` itself. The unit tests stand alone.
- FakeSession tests verify logic structure, not real Cypher syntax. Cypher correctness
  is not validated by Option A — that is acknowledged and deferred to Option B (follow-on).

## Repo Touchpoints

| File | Status |
| --- | --- |
| `research/bin/qa_graph_integrity.sh` | exists — reference only; do not modify |
| `tests/unit/test_graph_integrity.py` | new |
| `.github/workflows/test-integrity.yml` | new |
| `Makefile` | exists — add `test-integrity` target here |

## In Scope
- `tests/unit/test_graph_integrity.py` — 5 unit tests mirroring the 5 shell checks
- CI workflow `.github/workflows/test-integrity.yml` that runs these tests
- `Makefile` target `make test-integrity` for local invocation
- GitHub Actions workflow status badge added to `qws_graph/README.md`

## Out of Scope
- Full integration test suite against live Neo4j (Option B — follow-on)
- Seeding fixtures for all 9 Epic 3 UAT phases
- Performance benchmarking
- Modifying `qa_graph_integrity.sh`

## Acceptance Criteria
- [ ] `make test-integrity` runs the 5 integrity unit tests and exits 0 on a clean codebase.
- [ ] Intentionally breaking a champion property (remove `metrics_sharpe`) causes the
  relevant test to fail.
- [ ] CI runs `make test-integrity` on every push to `feature/*` and `main`.
- [ ] GitHub Actions workflow status badge is added to `qws_graph/README.md` linking to
  the `test-integrity` workflow.

## Definition of Done
- [ ] Unit tests implemented (5 checks, using `downstream_champions` or direct Cypher — not `trace_champion`).
- [ ] CI workflow step added.
- [ ] `Makefile` target documented.
- [ ] Story marked CLOSED.
