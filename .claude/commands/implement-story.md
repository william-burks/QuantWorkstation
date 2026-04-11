Implement the QuantWorkstation story identified by: $ARGUMENTS

## Step 0 — Read memory (MANDATORY FIRST)
Read `.claude/agent-memory/lead-engineer/MEMORY.md` and all referenced files BEFORE any tool invocations.
Use the exact commands documented there for tests, lint, and type checking.
Do NOT attempt ruff, pytest, or mypy without checking memory for the correct invocation.

## Step 1 — Locate story
Search `qws_graph/epics/` for story `$ARGUMENTS`. Read full file.
Stop if Status ≠ `ready`.
**Story file is now in context — do NOT re-read it during Steps 4 or 7.**

## Step 2 — Verify unblocked
Read `docs/BACKLOG_ALIGNMENT.md` "Blocked On" column. If blocked → stop, report blocker.

## Step 3 — Read context
Read docs directly (known locations):
- `docs/PROVENANCE_ENGINE.md`
- `docs/BACKLOG_ALIGNMENT.md`

**PROVENANCE_ENGINE.md and BACKLOG_ALIGNMENT.md are now in context — do NOT re-read them in any later step.**

For story's "Repo Touchpoints" source files, use this exact recipe:
1. `mcp__codebase-memory-mcp__search_code(query="function_or_class_name")` → note the qualified_name from result
2. `mcp__codebase-memory-mcp__get_code_snippet(qualified_name=...)` → read that section only, done
Do NOT grep or Read entire files to orient. Do NOT run multiple search_code calls for the same symbol.

No [TARGET] nodes/relationships/MCP tools unless this story implements them.

**STOP — do NOT re-read any of these files in later steps: PROVENANCE_ENGINE.md, BACKLOG_ALIGNMENT.md, story file.**

If any schema, design, or scope question cannot be resolved from these docs → do not guess.
```
echo "<exact question>" > /tmp/assumption_$ARGUMENTS.txt
git add <story file>
git commit -m "blocked($ARGUMENTS): assumption — <exact question>"
```
Report: `BLOCKED | assumption | <exact question>` and stop.

If `/tmp/ruling_$ARGUMENTS.txt` exists → read it before reporting blocked. Apply ruling and continue.

## Step 4 — Implement
Work ACs one by one. After each:
1. `- [ ]` → `- [x]` in story file
2. `git add` each changed file (never `-A` or `.`)
3. `make test` after any Python change — fix all failures
4. Run `mypy --strict` on changed files. Read ALL errors, fix ALL in one pass, re-run once. Max 2 cycles.

For large files (>500 lines): grep for the target function/section first, then read only that range.
Do NOT read whole files in sequential chunks.

Run `ruff check` once → collect ALL errors → fix ALL in one pass → re-run once to confirm. Max 2 cycles. Do NOT fix one error, re-run, fix the next.

**4b — Demo seed.** If this story adds or modifies nodes, edges, or properties:
update `DEMO_SEED_CYPHER` and `DEMO_TEARDOWN_CYPHER` in `qws_graph/research/graph/cypher.py`.
`cypher.py` is ~700 lines — grep for `DEMO_SEED_CYPHER` first (~line 465), then Read that offset range only. Do NOT read the whole file. Do NOT re-read cypher.py after this step.
New node types → add MERGE block (`is_demo=true`, deterministic IDs, realistic values).
Modified properties → update existing SET blocks. This is part of implementation, not verification.

## Step 5 — Write Acceptance Test Plan
Add `## Acceptance Test Plan` section to story file after ACs.

```markdown
### AC1: <description>
- type: cli | cypher | file_check | regression
- cmd: <exact command>
- expect_contains: "<substring>"
- expect_exit: 0
```

Types: `cli` (qw command + exit/output), `cypher` (Neo4j query + result), `file_check` (path exists/content), `regression` (two commands match).

Rules: demo seed IDs only. Never real data. Generate fixtures/scripts as needed. Every AC ≥ 1 test step.

## Step 6 — Commit implementation
```
git add <files by name>
git commit -m "impl($ARGUMENTS): <summary>"
```

## Step 7 — Execute acceptance tests (fail/fix cycle)
Run each test step. Compare actual vs expected.

Passing AC → confirm `- [x]`.

**On failure:**
1. Mark AC: `- [FAILED] AC<N> — <actual vs expected>`
2. `git commit -m "fail($ARGUMENTS): AC<N> — <failure>"`
3. Diagnose + fix code
4. Restore `- [x]`
5. `git commit -m "fix($ARGUMENTS): AC<N> — <what fixed>"`
6. Re-run ALL tests from top
7. Max 3 cycles → commit blocked state + stop:
   ```
   git add <story file>
   git commit -m "blocked($ARGUMENTS): AC<N> — max cycles, <reason>"
   ```
   Report: `BLOCKED | <reason>` and stop.

## Step 8 — Update status
All ACs pass → READY → TESTING in story, INDEX.md, BACKLOG_ALIGNMENT.md.
```
git add <story> qws_graph/epics/INDEX.md docs/BACKLOG_ALIGNMENT.md
git commit -m "status($ARGUMENTS): READY → TESTING"
```

## Step 9 — Report

```
## $ARGUMENTS — Implemented and Self-Tested

### Changes
[file-by-file bullets]

### Acceptance Tests
| AC | Status | Notes |
|----|--------|-------|

### Fix cycles
[fail/fix commits if any]

### Quality
[pytest result]

### Generated test data
[new fixtures/scripts]
```

Final: **CLOSED-READY** or **BLOCKED** (with details). Do not mark CLOSED.