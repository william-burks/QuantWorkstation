---
name: QuantWorkstation tooling commands
description: Exact shell commands for lint, test, and seed operations — use these verbatim
type: project
---

## Lint (from project root)
```
make lint
```
Do NOT use `ruff check` or `python -m ruff` directly. `make lint` runs ruff check + format. `make verify` runs lint + typecheck + test-all.

## Tests
```
make test          # qws_graph/tests/unit/
make test-unit     # tests/unit/
make test-all      # both suites
make test-integration  # qws_graph/tests/integration/
```
All make targets handle venv activation — never invoke pytest directly.

## Demo seed
```
qw seed --demo
qw seed --demo --teardown
```

## Story test file map (AUTHORITATIVE — use these exact paths)
NEVER ls for test files. NEVER use paths not in this table.
If a story is not in this table, skip its per-story test step.

| Story | Test file |
|-------|-----------|
| QWS-0601 | qws_graph/tests/unit/test_hypothesis_journaling.py |
| QWS-0602 | tests/unit/test_stability.py |
| QWS-0603 | tests/unit/test_portfolio_correlation.py |
| QWS-0604 | qws_graph/tests/unit/test_store_semantic.py qws_graph/tests/unit/test_qw_hypothesis_similarity.py |

Top-level `tests/unit/` contains data/execution tests only. Most qws_graph story tests live in `qws_graph/tests/unit/`.

## Pre-existing failures
Some tests may fail due to environment (pandas import, Neo4j connection, ibkr_futures_collector, etc.).
Do NOT debug environment failures. Record them and move on.
Never retry the same command more than once.

## Ruff output format
Ruff errors look like this (arrow lines point to the file):
```
E501 Line too long (167 > 100)
  --> data/collectors/ibkr_futures.py:43:101

F401 [*] `typing.Any` imported but unused
  --> qws_graph/research/graph/query_presets.py:6:1
```
The summary line at the end: `Found 416 errors.`
A clean run ends with: `Found 0 errors.` or no "Found" line (straight to mypy).

**Fixable codes:** F401 (unused import), F841 (unused variable), I001 (import sort).
**Skip ALL other codes** — E402, E501, and any E-code are pre-existing project-wide noise. Do NOT investigate or grep for them.

**To extract in-scope errors from the tee file, use this ONE command (no pipes):**
```
grep -E "^\s*-->" /tmp/qa_epic_EPIC_lint.txt
```
Output: `  --> file:line:col` for every error. Cross-reference against `git diff` changed files. Do NOT use any other grep pattern. Do NOT pipe through sed or sort — read the output directly. Do NOT grep with -A, -B, -C, or for specific error codes. If you need error context, Read the lint tmp file directly.

**To verify lint is clean after fixes:**
```
make lint 2>&1 | tail -5
```
Check for `Found 0 errors` in the output. That's your clean signal — no parsing needed.

## Scope filter (only epic-touched files)
```
git diff feature/26.4.0/QWS-0301..HEAD --name-only
```
Use this to identify which lint errors are in-scope vs pre-existing. Do NOT use `main` — the base branch is `feature/26.4.0/QWS-0301`.

## Demo seed file
`qws_graph/research/graph/cypher.py` is >300 lines (11959 tokens). Use offset+limit to read in chunks. First chunk: offset=0, limit=400 (covers all queries up to DEMO_SEED_CYPHER). Second chunk: offset=400 covers DEMO_SEED_CYPHER. Two reads total.

## Epic 7 story test map (add to table above)
| QWS-0801 | qws_graph/tests/unit/test_store_former_champion.py qws_graph/tests/unit/test_qw_degrade_retire.py |
| QWS-0703 | qws_graph/tests/unit/test_analyst.py |
| QWS-0804 | qws_graph/tests/unit/test_gate_recheck.py |

## Epic 8 story test map (add to table above)
| QWS-0802 | qws_graph/tests/unit/test_store_dedup.py |
| QWS-0803 | qws_graph/tests/unit/test_monitor.py |
| QWS-0805 | qws_graph/tests/unit/test_graph_query_models.py |

## qws_graph tests require venv
Use `make test` or `make test-all` — both handle venv. If running a single file: `source .venv/bin/activate && pytest qws_graph/tests/unit/<file> -v`
