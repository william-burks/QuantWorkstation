---
name: Project tooling and commands
description: How to run tests, lint, and type-check in QuantWorkstation — venv activation, Makefile targets, common patterns
type: project
---

## Test/Lint Commands

All commands require venv activation: `source .venv/bin/activate`
ALWAYS run from project root `/Users/will/ClaudeProjects/QuantWorkstation` — NOT from `qws_graph/`.

- **Unit tests:** `make test` or `source .venv/bin/activate && pytest qws_graph/tests/unit/ -v`
- **Lint:** `source .venv/bin/activate && ruff check qws_graph/path/to/file.py`
- **Type check:** `source .venv/bin/activate && mypy --strict qws_graph/path/to/file.py`
- **Both:** `make check`
- **Neo4j status:** `make -C qws_graph neo4j-status`

Do NOT use `cd qws_graph && ruff check research/...` — breaks import resolution.
Do NOT use `python -m ruff` — use `ruff` directly after venv activation.

## Mypy Fix Protocol

Run mypy once, read ALL errors, fix ALL in one pass, re-run once to confirm. Max 2 cycles.
Never fix-one-rerun-fix-one — that wastes 3x the tool calls.
Do NOT run mypy on individual files after a batch pass — if batch passed, you are done.

## Ruff / Lint Protocol

Lint is deferred to QA phase. Do NOT run ruff at any point during implementation.
`ruff`, `make lint`, and `make check` are structurally blocked by agent-guard.sh — attempting them will error.
Type checking only: `make typecheck` (mypy --strict). Ruff runs happen post-epic via qa-engineer → lint-mechanic.

## Key File Sizes & Grep-First Targets

Large files — grep for function/section names first, read only that range. Do NOT read sequentially.

| File | Lines | Key landmarks |
|------|-------|---------------|
| `qws_graph/research/graph/store.py` | ~1400 | grep for method names like `record_hypothesis`, `backfill_embeddings` |
| `qws_graph/research/graph/cli.py` | ~1500 | grep for subcommand decorators like `@app.command` |
| `qws_graph/research/graph/cypher.py` | ~700 | `DEMO_SEED_CYPHER` starts ~line 465, `DEMO_TEARDOWN_CYPHER` follows |
| `qws_graph/research/graph/query.py` | ~540 | Cypher constant strings at bottom (~line 500+) |
| `qws_graph/docs/data_dictionary.yaml` | ~1060 | `Hypothesis:` section starts ~line 840 |

## Demo Seed

When adding new nodes/edges/properties, update BOTH:
- `DEMO_SEED_CYPHER` in `qws_graph/research/graph/cypher.py` — MERGE blocks with `is_demo=true`, deterministic IDs
- `DEMO_TEARDOWN_CYPHER` — matching cleanup

Do this during implementation (implement-story Step 4b), not verification.

## Codebase Discovery (codebase-memory-mcp)

For finding functions, classes, or understanding file structure — use MCP tools FIRST:
- `search_code(query="record_hypothesis")` → finds function location without reading whole file
- `get_code_snippet(qualified_name="GraphStore.record_hypothesis")` → reads just that function
- `trace_call_path(source="backfill_embeddings")` → shows what calls what

Only fall back to Grep/Read when:
- Graph is not indexed (run `index_repository` first)
- You need to read a config/doc file at a known path (just use Read directly)

## Integration Tests

Pre-existing failures may exist in `qws_graph/tests/integration/`. Do not git stash to check baseline —
if a test fails that doesn't touch your code paths, note it and move on.
