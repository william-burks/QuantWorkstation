Verify test sweep for QuantWorkstation story: $ARGUMENTS

## Step 1 — Locate story
```bash
bash .claude/scripts/agent-init-state.sh verify-story
STORY_FILE=$(.claude/scripts/locate-story.sh $ARGUMENTS)
```
If exit 1 → report BLOCKED (story not found).
Read the file at `$STORY_FILE`. Stop if Status ≠ `TESTING`.

## Step 2 — Unit tests
```
make test-all 2>&1
```
Record pass/fail/error/skip. On failure: diagnose (test bug vs code bug), fix, re-run until clean.

## Step 3 — Audit fixtures
Read `docs/PROVENANCE_ENGINE.md` — note nodes/relationships/fields from this story.

**3a — Update stale:** Compare fixtures in `qws_graph/tests/fixtures/` against schema. Fix stale fields.
**3b — Create missing:** New node/relationship types need fixtures in appropriate subdir (`baseline/`, `champion/`, `grid/`, `tracker/`). Name: `<symbol>_<direction>_<tf>_<variant>`. Add unit test for new fixtures.

## Step 4 — Verify demo seed (not create)
Read `qws_graph/research/graph/cypher.py` DEMO_SEED_CYPHER + DEMO_TEARDOWN_CYPHER.
Demo seed should already be updated from implement-story Step 4b. Verify consistency:
- New nodes/edges from this story present in MERGE blocks with `is_demo=true`
- Modified properties reflected in SET blocks
- DEMO_TEARDOWN_CYPHER cleans up everything DEMO_SEED_CYPHER creates
- Cypher syntax correct (brackets, commas, strings)
If demo seed is missing or inconsistent → fix it, but note this as a gap in implementation.

## Step 5 — Integration tests
If tests in `qws_graph/tests/integration/` cover this story's code paths:
```
make test-integration 2>&1 | grep -E "<relevant>"
```
Neo4j unreachable → note "skipped", continue.

## Step 6 — E2E smoke
Check `qws_graph/tests/e2e/run_e2e.py` for matching scenarios. List for reference — do not execute.

## Step 7 — Verify DoD
For each DoD item: automatable → verify now. Requires live env → flag.

Run type-check from **project root** (not `qws_graph/`):
```
make typecheck
```
Baseline is clean (0 errors). Any failure = introduced by this story. Fix all. To verify edits landed, read the file — do not grep a file you just edited.

## Step 7b — Re-run Acceptance Tests
If story has `## Acceptance Test Plan`:
1. Execute each test step (same commands as implement-story Step 7)
2. All pass → confirm all ACs `- [x]`
3. On failure → diagnose + fix code, `git commit -m "verify-fix($ARGUMENTS): <what fixed>"`, re-run. Max 2 fix cycles.
Any `- [ ]` or `- [FAILED]` after fix cycles → note in "Remaining before CLOSED."

## Step 8 — Update DoD checkboxes
Check off verified items. Leave unchecked only items requiring manual verification.

## Step 9 — Stage and commit
```
git add <test files> <fixtures> <cypher.py if changed> <story file>
make commit-test STORY=$ARGUMENTS
```
Never `git add -A` or `git add .`.

## Step 10 — Report and STOP

**STOP GATE: Step 9 committed → output report below and STOP. No further tool calls. No exceptions.**

The orchestrator invokes close-story — you do NOT. Do not read close-story.md, do not change story Status, do not run agent-init-state.sh.

```
## $ARGUMENTS — Verification Report

### Test sweep
- Unit: X pass / Y fail / Z skip
- Integration: pass | skipped | N/A
- Ruff/mypy: clean | <fixed>

### Fixtures
- Updated: [files, what was stale]
- Created: [files, what shape]

### Demo seed (cypher.py)
- [MERGE blocks touched, properties added/changed/removed]

### DoD verified
[checked items]

### DoD remaining (manual)
[unchecked items with exact commands]

### Remaining before CLOSED
[blockers or empty]
```