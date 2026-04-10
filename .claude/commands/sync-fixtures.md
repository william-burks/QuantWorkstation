Audit and sync test fixtures for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story and schema
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Read full file.
Read `docs/PROVENANCE_ENGINE.md` — note every node type, relationship type, and field name
introduced or modified by this story.

## Step 2 — Update stale fixtures
For each fixture file under `qws_graph/tests/fixtures/`:
1. Open and compare field names against current schema
2. If any field is stale (old name, removed field, wrong type), update in place

## Step 3 — Create missing fixtures
For each new node type, relationship type, or data shape introduced by this story:
1. Check all four subdirectories:
   `artifacts/baseline/`, `artifacts/champion/`, `artifacts/grid/`, `artifacts/tracker/`
2. If no fixture covers it, create one:
   - Place in subdirectory whose purpose best matches
   - Name: `<symbol>_<direction>_<tf>_<variant>.md` (or `.json`/`.yaml`) following existing conventions
   - Populate with realistic but minimal data — enough to exercise new fields
3. If new shape is structural (new Python dataclass or graph node), add/update unit test in
   `tests/unit/` that loads fixture and asserts new fields

## Step 4 — Stage changes
```
git add <fixture files updated or created>
git add <unit test files updated or created>
```
Never `git add -A` or `git add .`.

## Step 5 — Report
```
## $ARGUMENTS — Fixture Sync Report

### Updated fixtures
- <file>: <what was stale, what changed>

### Created fixtures
- <file>: <shape it covers>

### Unit tests added/updated
- <file>: <what it asserts>

### No changes needed
- <files checked with no issues>
```
