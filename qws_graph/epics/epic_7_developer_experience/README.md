# Epic 7 — Developer Experience

## Objective
Remove the remaining friction from the research-to-graph workflow. Packaging, automation,
and quality gates that make the system faster and safer to operate day-to-day.

## Why it exists
By the time Epic 6 is complete, the graph is a fully-featured research index with context
enrichment, analytics tools, and a research journal. The remaining friction is operational:
- Shared strategy utility code can't be reused across repos without vendoring.
- The graph integrity QA check (`qa_graph_integrity.sh`) is manual — no automated gate
  catches regressions before they compound.

These are not research problems. They are engineering hygiene problems that compound in
cost the longer they're deferred.

## Stories
1. `QWS-0701` `story_1_pypi_packaging.md` — package `strategy_utils` for PyPI
2. `QWS-0702` `story_2_ci_graph_integrity.md` — automated CI graph integrity gate

These stories are independent of each other and of earlier epics.

## Dependencies
- No dependency on Epics 4–6.
- Story 1 depends only on the existing `strategies/common/` helpers being stable.
- Story 2 depends on Neo4j test fixtures being available in CI (or a mock graph approach).

## Exit Criteria
- `strategy_utils` package is importable from PyPI (or TestPyPI) and passes `twine check`.
- `qa_graph_integrity.sh` (or its CI equivalent) runs automatically on every push to
  the feature branch and fails the build if any check fails.
