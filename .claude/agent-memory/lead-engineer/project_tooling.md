---
name: Project tooling and commands
description: How to run tests, lint, and type-check in QuantWorkstation — venv activation, Makefile targets, common patterns
type: project
---

## Test/Lint Commands

All commands require venv activation: `source .venv/bin/activate`
ALWAYS run from project root `/Users/will/ClaudeProjects/QuantWorkstation` — NOT from `qws_graph/`.

- **qws_graph unit tests:** `make test`
- **main unit tests:** `make test-unit`
- **both suites:** `make test-all`
- **integration tests:** `make test-integration`
- **type check:** `make typecheck` (bare mypy is blocked)
- **Neo4j status:** `make -C qws_graph neo4j-status`

All make targets handle venv activation — never invoke pytest or ruff directly.

## Mypy Fix Protocol

Use `make typecheck` ONLY. Bare `mypy` is structurally blocked by agent-bash-grep-guard.sh —
ALL bare mypy invocations (file, directory, or piped) are rejected. `mypy file.py`,
`mypy --strict qws_graph/` and `mypy --strict dir/ | awk` will all be blocked.
Baseline is **0 errors** — any failure = you introduced it. Run `make typecheck` once, fix ALL in one pass, re-run once. Max 2 cycles. Never fix-one-rerun-fix-one.

## Ruff / Lint Protocol

Lint is deferred to QA phase. Do NOT run ruff at any point during implementation.
`ruff`, `make lint`, and `make check` are structurally blocked by agent-guard.sh — attempting them will error.
Type checking only: `make typecheck` (mypy --strict). Ruff runs happen post-epic via qa-engineer → lint-mechanic.

## Key File Sizes & Grep-First Targets

Large files — grep for function/section names first, read only that range. Do NOT read sequentially.

| File | Lines | Key landmarks |
|------|-------|---------------|
| `qws_graph/research/graph/store.py` | ~1400 | grep for method names like `record_hypothesis`, `backfill_embeddings` |
| `qws_graph/research/graph/cli.py` | ~1550 | `argparse` CLI — NOT click/typer. `def cmd_*` handlers start ~L312. Parser registration via `subparsers.add_parser()` starts ~L1346. To add a new subcommand: grep `add_parser` for registration section, read L1340-L1400 range. |
| `qws_graph/research/graph/cypher.py` | ~700 | `DEMO_SEED_CYPHER` starts ~line 465, `DEMO_TEARDOWN_CYPHER` follows |
| `qws_graph/research/graph/query.py` | ~540 | Cypher constant strings at bottom (~line 500+) |
| `qws_graph/docs/data_dictionary.yaml` | ~1100 | Use schema-index.txt — never read full file. `grep 'NodeType' /tmp/schema-index.txt` → offset. Compose entire node/edge block in ONE Edit call. Max 2 edits total. |

## Demo Seed

When adding new nodes/edges/properties, update BOTH:
- `DEMO_SEED_CYPHER` in `qws_graph/research/graph/cypher.py` — MERGE blocks with `is_demo=true`, deterministic IDs
- `DEMO_TEARDOWN_CYPHER` — matching cleanup

Do this during implementation (implement-story Step 4b), not verification.

## Story File Location

Story filenames do NOT contain the QWS-NNNN ID. Always use content search:
```bash
grep -rl 'QWS-0801' qws_graph/epics/
```
Do NOT glob for the ID — it won't match filenames. Do NOT use Glob `**/*0801*`.

## Codebase Discovery (codebase-memory-mcp)

MCP project name: `Users-will-ClaudeProjects-QuantWorkstation` — required for ALL MCP calls.

Discovery order for Python functions/classes (stop at first hit):
1. `search_graph(project="Users-will-ClaudeProjects-QuantWorkstation", label="Function", name_pattern="symbol_name")` → note `qualified_name` + `start_line` → `get_code_snippet(project="Users-will-ClaudeProjects-QuantWorkstation", qualified_name=...)`. Uncapped. Returns exact line range.
2. `grep 'symbol_name' /tmp/symbol-index.txt` — fallback when graph misses (constants, config vars, unindexed). Gives `file.py:lineN`, read 50-line range.
3. One targeted Grep — last resort only.

For cli.py full anchor map (one call): `search_graph(project="Users-will-ClaudeProjects-QuantWorkstation", label="Function", file_pattern="*cli.py", limit=50)`

For data_dictionary.yaml (YAML not indexed by MCP — use schema-index):
`grep 'NodeOrEdgeName' /tmp/schema-index.txt` → get line N → `Read data_dictionary.yaml offset=N limit=40`
schema-index.txt is built at Step 0 alongside symbol-index.txt.

Notes:
- `file_pattern` is glob-to-LIKE: `*` prefix mandatory (`cli.py` → 0 results, `*cli.py` → 18 results)
- Always pass `limit` — default is 500,000 rows
- `qn_pattern` is dotted-name regex (e.g. `.*graph.store.*`), NOT a file filter — don't confuse with `file_pattern`

Only fall back to Grep/Read when:
- Graph is not indexed (run `index_repository` first)
- You need to read a config/doc file at a known path (just use Read directly)

## Step 8 — Atomic Status Commit

Use `make commit-story-status STORY=$ID` — stages all modified tracked files, commits, and arms the phase gate in one atomic call.
Optional custom message: `make commit-story-status STORY=$ID MSG="custom message"`.
Do NOT run git add or echo the sentinel separately — the make target handles both.

## Integration Tests

Pre-existing failures may exist in `qws_graph/tests/integration/`. Do not git stash to check baseline —
if a test fails that doesn't touch your code paths, note it and move on.
