Verify the test sweep for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate and verify status
Find the story file in `qws_graph/epics/` containing ID `$ARGUMENTS`.
Read the full story file.

If Status is not `TESTING`, stop and report:
- Current status
- What must happen before this story can be verified (must be implemented first)

## Step 2 — Run unit tests
```
pytest tests/unit/ -v 2>&1
```
Record: total passed, failed, errored, skipped.

If any test **fails**, do not proceed. Diagnose the failure:
1. Read the failing test and the code it exercises
2. If the failure is a test bug (wrong expectation after a legitimate schema change), fix the test
3. If the failure is a code bug, fix the code
4. Re-run until clean
Report every fix made.

## Step 3 — Audit and update fixtures
Read `docs/PROVENANCE_ENGINE.md` — note every node type, relationship type, and field name
introduced or modified by this story.

### 3a — Update stale fixtures
For each fixture file under `qws_graph/tests/fixtures/`:
1. Open the file and compare field names against the current schema
2. If any field is stale (old name, removed field, wrong type), update it in place

### 3b — Create missing fixtures
For each new node type, relationship type, or data shape introduced by this story:
1. Check whether a fixture already covers it — look in all four subdirectories:
   `artifacts/baseline/`, `artifacts/champion/`, `artifacts/grid/`, `artifacts/tracker/`
2. If no fixture covers it, create one that exercises the new shape:
   - Place it in the subdirectory whose purpose best matches (champion = best-result artifacts,
     grid = sweep outputs, baseline = reference runs, tracker = OOS/ongoing tracking)
   - Name it `<symbol>_<direction>_<tf>_<variant>.md` (or `.json` / `.yaml`) following existing
     naming conventions in that directory
   - Populate it with realistic but minimal data — enough to exercise the new fields
3. If the new shape is structural (a new Python dataclass or graph node), also add or update a
   corresponding unit test in `tests/unit/` that loads the fixture and asserts the new fields

Log every fixture file checked, updated, or created.

## Step 4 — Sync demo seed nodes
Read `qws_graph/research/graph/cypher.py`, specifically `DEMO_SEED_CYPHER` and `DEMO_TEARDOWN_CYPHER`.

For every node type modified or extended by this story:
1. Find the matching MERGE block(s) in `DEMO_SEED_CYPHER`
2. Check that every new property the story introduced is present in the `SET` block
3. If a property is missing, add it with a realistic demo value consistent with the node's
   role (e.g., demo-strategy-alpha is the "active institutional" case — values should reflect that)
4. If the story introduced a new node type entirely, add a new MERGE block following the
   existing pattern (`is_demo=true`, deterministic IDs like `'demo-...'`, realistic values)
5. If the story removed or renamed a property, remove/rename it in every affected MERGE block

After editing `cypher.py`, verify the Cypher is syntactically consistent by reading it back
and checking for mismatched brackets or missing commas.

Log every MERGE block touched and what changed.

## Step 5 — Run integration tests (if applicable)
Check whether any test in `qws_graph/tests/integration/` covers code paths touched by this story.
If yes:
```
pytest qws_graph/tests/integration/ -v -k "<relevant test names>" 2>&1
```
Integration tests require a live Neo4j instance. If Neo4j is not reachable, note "integration
tests skipped — Neo4j not available" and continue.

## Step 6 — Run e2e smoke (if applicable)
Check `qws_graph/tests/e2e/run_e2e.py` — if the story's Acceptance Criteria map to any e2e
scenario, note which ones. Do NOT execute automatically — list what Will should run manually.

## Step 7 — Verify Definition of Done items are checkable
Re-read the story's Definition of Done section.
For each item:
- If it is automatable (pytest, ruff, mypy), verify it now
- If it requires Will's environment (live Neo4j, manual CLI walk), flag it explicitly

Run ruff and mypy on any Python files touched by this story:
```
ruff check <files> && mypy --strict <files> 2>&1
```
Fix all warnings before continuing.

## Step 8 — Update Definition of Done checkboxes
In the story file, check off every DoD item you verified in Steps 2–7.
Leave unchecked only items that require Will's manual verification.

## Step 9 — Stage changed files
```
git add <any test files fixed>
git add <any fixture files updated or created>
git add qws_graph/research/graph/cypher.py   # if demo seed was updated
git add <story file>
```
Never use `git add -A` or `git add .`.

## Step 10 — Report
```
## $ARGUMENTS — Verification Report

### Test sweep
- Unit: X passed / Y failed / Z skipped
- Integration: passed | skipped (reason) | N/A
- Ruff/mypy: clean | <issues fixed>

### Fixtures
- Updated: [list of files changed, what was stale]
- Created: [list of new fixtures, what shape they cover]

### Demo seed nodes (cypher.py)
- [list of MERGE blocks touched and what properties were added/changed/removed]
- No changes needed | N/A

### DoD items verified automatically
[checked list]

### DoD items requiring Will's manual verification
[exact commands Will must run, with expected output]

### Remaining before CLOSED
[list anything still blocking close; empty = ready to close]
```

Do not change the story Status field. That is Will's decision via /close-story.