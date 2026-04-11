Implement the QuantWorkstation story identified by: $ARGUMENTS

## Step 1 — Locate story
Search `qws_graph/epics/` for story `$ARGUMENTS`. Read full file.
Stop if Status ≠ `ready`.

## Step 2 — Verify unblocked
Read `docs/BACKLOG_ALIGNMENT.md` "Blocked On" column. If blocked → stop, report blocker.

## Step 3 — Read context
Read before coding:
- Story's "Repo Touchpoints" files
- `docs/PROVENANCE_ENGINE.md`
- `docs/BACKLOG_ALIGNMENT.md`

No [TARGET] nodes/relationships/MCP tools unless this story implements them.

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
3. `pytest tests/unit/ -v` after any Python change — fix all failures

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