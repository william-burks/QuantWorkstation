---
name: Project tooling and commands
description: How to run tests, lint, and type-check in QuantWorkstation — venv activation, Makefile targets, common patterns
type: project
---

## Test/Lint Commands

All commands require venv activation: `source .venv/bin/activate`

- **Unit tests:** `make test` or `source .venv/bin/activate && pytest qws_graph/tests/unit/ -v`
- **Lint:** `make lint` or `source .venv/bin/activate && ruff check <files> && mypy --strict <files>`
- **Both:** `make check`
- **Neo4j status:** `make -C qws_graph neo4j-status`

## Demo Seed

When adding new nodes/edges/properties, update BOTH:
- `DEMO_SEED_CYPHER` in `qws_graph/research/graph/cypher.py` — MERGE blocks with `is_demo=true`, deterministic IDs
- `DEMO_TEARDOWN_CYPHER` — matching cleanup

Do this during implementation (implement-story Step 4b), not verification.

## Integration Tests

Pre-existing failures may exist in `qws_graph/tests/integration/`. Do not git stash to check baseline —
if a test fails that doesn't touch your code paths, note it and move on.
