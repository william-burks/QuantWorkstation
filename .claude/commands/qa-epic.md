Post-epic QA review for QuantWorkstation epic: $ARGUMENTS

Invoke skill: caveman

Run on `release/yy.m.v` branch after all stories merged. Review every CLOSED story for regressions and consistency.

Tmp files used for context efficiency — written as results arrive, read at report time, cleaned up at end.
- Baseline: `/tmp/qa_epic_$ARGUMENTS_baseline.txt`
- Per story: `/tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt`
- Regression snapshot: `/tmp/qa_epic_$ARGUMENTS_current.txt`

## Step 0 — Baseline
```
qw seed --demo
pytest tests/unit/ -v 2>&1 | tee /tmp/qa_epic_$ARGUMENTS_baseline.txt
```
Any failure here is pre-existing — not caused by this epic's stories.

## Step 1 — Identify stories
Read `qws_graph/epics/INDEX.md` — find all CLOSED stories in epic $ARGUMENTS.
List story IDs and paths (in `closed/` subdirectory).

## Step 2 — Per-story review
For each CLOSED story, write all results to `/tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt` as they complete.

### 2a — Re-run Acceptance Test Plan
Execute every test step in `## Acceptance Test Plan`. Append results to story tmp file.

### 2b — Unit tests
```
pytest tests/unit/ -v -k "<story-related tests>" 2>&1 >> /tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt
```

### 2c — Static analysis
```
ruff check <story-touched files> && mypy --strict <story-touched files> 2>&1 >> /tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt
```
Fix any warnings found.

### 2d — Fixture consistency
Compare fixtures in `qws_graph/tests/fixtures/` against `docs/PROVENANCE_ENGINE.md`.
Append findings to story tmp file.

### 2e — Demo seed consistency
Read `qws_graph/research/graph/cypher.py`. Verify MERGE blocks match current schema.
Append findings to story tmp file.

### 2f — Cross-story regressions
```
pytest tests/unit/ -v 2>&1 | tee /tmp/qa_epic_$ARGUMENTS_current.txt
diff /tmp/qa_epic_$ARGUMENTS_baseline.txt /tmp/qa_epic_$ARGUMENTS_current.txt
```
Any `FAILED` line in current not present in baseline → cross-story regression. Flag with story that likely caused it.

## Step 3 — Fix issues
If issues found: fix code/fixtures/Cypher as needed.

## Step 4 — Commit and push
```
git add <fixed files>
git commit -m "qa(epic-$ARGUMENTS): post-epic QA fixes"
git push origin <release branch>
```
If no issues → skip commit, report clean.

## Step 5 — Teardown and cleanup
```
qw seed --demo --teardown
rm /tmp/qa_epic_$ARGUMENTS_*.txt
```

## Step 6 — Report
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