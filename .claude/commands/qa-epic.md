Post-epic QA review for QuantWorkstation epic: $ARGUMENTS

Invoke skill: caveman

Run on `release/yy.m.v` branch after all stories merged. Review every CLOSED story for regressions and consistency.

## Step 1 — Identify stories
Read `qws_graph/epics/INDEX.md` — find all CLOSED stories in epic $ARGUMENTS.
List story IDs and paths (in `closed/` subdirectory).

## Step 2 — Per-story review
For each CLOSED story:

### 2a — Re-run Acceptance Test Plan
Read story file. If `## Acceptance Test Plan` exists, execute every test step.
Flag any regression (test that previously passed now fails).

### 2b — Unit tests
```
pytest tests/unit/ -v -k "<story-related tests>" 2>&1
```
Record results. Flag failures.

### 2c — Static analysis
```
ruff check <story-touched files> && mypy --strict <story-touched files> 2>&1
```
Fix warnings.

### 2d — Fixture consistency
Compare fixtures in `qws_graph/tests/fixtures/` against `docs/PROVENANCE_ENGINE.md`.
Flag stale or missing fields.

### 2e — Demo seed consistency
Read `qws_graph/research/graph/cypher.py`. Verify MERGE blocks match current schema.

### 2f — Cross-story regressions
Run full test suite:
```
pytest tests/unit/ -v 2>&1
```
If any test fails that is NOT related to the current story → cross-story regression. Flag with story that likely caused it.

## Step 3 — Fix issues
If issues found: fix code/fixtures/Cypher as needed.

## Step 4 — Commit and push
```
git add <fixed files>
git commit -m "qa(epic-$ARGUMENTS): post-epic QA fixes"
git push origin <release branch>
```
If no issues → skip commit, report clean.

## Step 5 — Report
```
## Epic $ARGUMENTS — QA Report

### Per-story results
| Story | ACs | Unit | Ruff/mypy | Fixtures | Demo seed | Regressions |
|-------|-----|------|-----------|----------|-----------|-------------|

### Issues found and fixed
[list with commit ref]

### Outstanding issues
[any unfixed items]

### Verdict
CLEAN | ISSUES FIXED | ISSUES REMAINING
```