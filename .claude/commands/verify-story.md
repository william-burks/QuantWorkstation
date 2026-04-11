Verify test sweep for QuantWorkstation story: $ARGUMENTS

## Step 1 — Locate story
Find story `$ARGUMENTS` in `qws_graph/epics/`. Read full file.
Stop if Status ≠ `TESTING`.

## Step 2 — Unit tests
```
pytest tests/unit/ -v 2>&1
```
Record pass/fail/error/skip. On failure: diagnose (test bug vs code bug), fix, re-run until clean.

## Step 3 — Audit fixtures
Read `docs/PROVENANCE_ENGINE.md` — note nodes/relationships/fields from this story.

**3a — Update stale:** Compare fixtures in `qws_graph/tests/fixtures/` against schema. Fix stale fields.
**3b — Create missing:** New node/relationship types need fixtures in appropriate subdir (`baseline/`, `champion/`, `grid/`, `tracker/`). Name: `<symbol>_<direction>_<tf>_<variant>`. Add unit test for new fixtures.

## Step 4 — Sync demo seed
Read `qws_graph/research/graph/cypher.py` DEMO_SEED_CYPHER + DEMO_TEARDOWN_CYPHER.
- Modified node types → ensure new properties in SET blocks
- New node types → add MERGE block (`is_demo=true`, deterministic IDs, realistic values)
- Removed/renamed properties → update all affected MERGE blocks
- Verify Cypher syntax (brackets, commas, strings)

## Step 5 — Integration tests
If tests in `qws_graph/tests/integration/` cover this story's code paths:
```
pytest qws_graph/tests/integration/ -v -k "<relevant>" 2>&1
```
Neo4j unreachable → note "skipped", continue.

## Step 6 — E2E smoke
Check `qws_graph/tests/e2e/run_e2e.py` for matching scenarios. List for reference — do not execute.

## Step 7 — Verify DoD
For each DoD item: automatable → verify now. Requires live env → flag.
```
ruff check <files> && mypy --strict <files> 2>&1
```
Fix all warnings.

## Step 7b — Check Acceptance Test Plan
If story has `## Acceptance Test Plan`: verify all ACs are `- [x]`.
Any `- [ ]` or `- [FAILED]` → note in "Remaining before CLOSED."
Do not re-run acceptance tests.

## Step 8 — Update DoD checkboxes
Check off verified items. Leave unchecked only items requiring manual verification.

## Step 9 — Stage and commit
```
git add <test files> <fixtures> <cypher.py if changed> <story file>
git commit -m "test($ARGUMENTS): verification sweep — fixtures, demo seed, DoD"
```
Never `git add -A` or `git add .`.

## Step 10 — Report
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

Do not change story Status.