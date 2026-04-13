Post-epic QA review for QuantWorkstation epic: $ARGUMENTS

Run on `release/yy.m.v` branch after all stories merged. Review every CLOSED story for regressions and consistency.

Tmp files used for context efficiency — written as results arrive, read at report time, cleaned up at end.
- Baseline: `/tmp/qa_epic_$ARGUMENTS_baseline.txt`
- Per story: `/tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt`
- Regression snapshot: `/tmp/qa_epic_$ARGUMENTS_current.txt`

## Step -1 — Read memory (MANDATORY FIRST ACTION)
Read your agent memory at `.claude/agent-memory/qa-engineer/MEMORY.md` NOW.
Do this BEFORE any shell command, seed, or test. Do not skip this step.
If the Read is blocked by a hook, use `cat .claude/agent-memory/qa-engineer/MEMORY.md` instead.

### Critical rules (duplicated from memory — because memory reads get skipped)
- Lint: `make lint` only. Do NOT run `ruff check` or `python -m ruff` directly.
- Tests: `make test-all` (runs both suites). Single file: `source .venv/bin/activate && pytest <file> -v`
- Seed: `qw seed --demo` and `qw seed --demo --teardown`
- Never retry the same command more than once.
- Never debug environment failures (pandas import, Neo4j connection). Record and move on.
- Never `ls` for test files. Use the story test table in Step 2b.
- Never combine multiple commands in one Bash call with newlines. Use separate Bash calls.
- Never use `python3 -c` for inline scripts. Read the tmp file directly instead.
- Extract what you need on first read of a file. Do not re-read the same file within a run.
- After the Phase 2 STOP gate: do not read, grep, or reference ANY `/tmp/qa_epic_*` file, `cypher.py`, or `PROVENANCE_ENGINE.md`.
- Never run `git stash list`, `git stash show`, or investigate stash state.
- Run `git log` and `git diff --name-only` once each in Phase 2. Do not re-run them.
- Never run research scripts (`python -m research.*`, `python -m analytics.*`). QA checks tests and lint only.
- Never batch `rm` calls in parallel. Run each `rm` in its own sequential Bash call.

## Step 0 — Baseline
```
qw seed --demo
make test-all 2>&1 | tee /tmp/qa_epic_$ARGUMENTS_baseline.txt
```
Any failure here is pre-existing — not caused by this epic's stories.
If tests fail: record the failures and continue. Do NOT debug import errors or environment issues.
Only investigate failures that appear NEW in the regression diff (Step 2f).
Never retry the same command more than once.

## Step 1 — Identify stories
Read `qws_graph/epics/INDEX.md` — find all CLOSED stories in epic $ARGUMENTS.
List story IDs and paths (in `closed/` subdirectory).
Do not `ls` the epics directory — INDEX.md is the source of truth for story paths.

## Step 2 — Per-story review
For each CLOSED story, write all results to `/tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt` as they complete.

### 2-scope — Read scope boundary (FIRST action per story, before any test or grep)
Read the story file. Extract the `## In Scope` and `## Out of Scope` sections.
These define your review boundary for this story — you are DONE reading the story file after this step.
Do NOT grep for scope sections. Do NOT re-read the story file later in the review.
Write the scope boundary to the story tmp file as the first entry:
```
# Scope boundary
In scope: <list from story file>
Out of scope: <list from story file>
```
Only verify ACs, run tests, and check lint for items that appear in `## In Scope`. Skip anything in `## Out of Scope` without investigation.

### 2a — Re-run Acceptance Test Plan
Execute every test step in `## Acceptance Test Plan`. Append results to story tmp file.
**Skip any test step that runs research scripts (`python -m research.*`, `python -m analytics.*`) or requires a live Neo4j query** — these are validated by unit tests in Step 2b.

### 2b — Unit tests
Use these exact paths per story. Do NOT `ls` or guess paths.

| Story | Test file |
|-------|-----------|
| QWS-0601 | qws_graph/tests/unit/test_hypothesis_journaling.py |
| QWS-0602 | tests/unit/test_stability.py |
| QWS-0603 | tests/unit/test_portfolio_correlation.py |
| QWS-0604 | qws_graph/tests/unit/test_store_semantic.py |

Run each story's test file once. Do not re-run passing tests.
If you discover additional test files during the run, do NOT run them. ONLY the files in this table. No exceptions.
```
pytest <test_file> -v 2>&1 >> /tmp/qa_epic_$ARGUMENTS_<STORY_ID>.txt
```

### 2c — Static analysis

#### Phase 1: Capture lint output
```
make lint 2>&1 | tee /tmp/qa_epic_$ARGUMENTS_lint.txt
```
This is your ONLY `make lint` run. You do NOT fix lint errors — you write a fixlist.

#### Phase 2: Identify in-scope errors
Three steps. Each produces a file. Read files — do not re-grep.

**Step A — save changed files:**
```
git diff feature/26.4.0/QWS-0301..HEAD --name-only > /tmp/qa_epic_$ARGUMENTS_changed.txt
```

**Step B — save error code + file path pairs:**
Ruff format: error line, then `  --> file:line:col` below it. This captures BOTH lines together:
```
grep -B1 -E "^\s*-->" /tmp/qa_epic_$ARGUMENTS_lint.txt > /tmp/qa_epic_$ARGUMENTS_arrows.txt
```
WARNING: The `-B1` flag is mandatory. It captures the error code line printed ABOVE each `-->` line. Without `-B1`, arrows.txt has only file paths and Step C cannot identify fixable codes.
Each pair in arrows.txt: error code line on top, `-->` file path line below. You have everything you need.

**Step C — cross-reference (TWO Reads, then done — never touch lint.txt again):**
Use the Read tool (not Bash grep) for both files:
```
Read /tmp/qa_epic_$ARGUMENTS_changed.txt
Read /tmp/qa_epic_$ARGUMENTS_arrows.txt
```
Both files are now in context. Make ONE pass through arrows.txt from top to bottom:
- Each pair: error code line on top, `  --> file:line:col` below.
- For each pair: extract file path from `-->` line. Check if that path appears in changed.txt.
  - If file NOT in changed.txt → skip, move to next pair.
  - If file IS in changed.txt AND code is F401/F841/I001 → add to your scratch list.
  - If file IS in changed.txt but code is anything else (E402, E501, any E-prefix) → skip.
- When you reach the end of arrows.txt, you are DONE. Do NOT re-read arrows.txt. Do NOT re-read changed.txt. Do NOT grep either file. Do NOT go back to lint.txt.
One pass. No re-reads.

**STOP GATE: lint analysis complete → proceed to next action below. No lint tool calls. No exceptions.**

All `/tmp/qa_epic_*` lint files are off-limits from this point. The phase gate (agent-phase-gate.sh) blocks any further lint/ruff/grep on those files.

Next action:
- Fix list empty → skip Phase 3, proceed to Step 2d.
- Fix list has items → proceed to Phase 3.

#### Phase 3: Write fixlist (ONLY if errors found in-scope)
If Phase 2 found fixable errors in changed files:
1. Write them to `/tmp/qa_epic_$ARGUMENTS_fixlist.txt` in this exact format:
```
# Epic $ARGUMENTS — Lint Fix List
# Format: file:line:col | code | description
path/to/file.py:6:1 | F401 | `typing.Any` imported but unused
```
2. **STOP. Do NOT fix any lint errors.** The orchestrator will spawn lint-mechanic to handle fixes.
3. Proceed to Step 2d.

If Phase 2 found zero in-scope errors, skip Phase 3 entirely. Do NOT write an empty fixlist.

### 2d — Schema context + Fixture consistency
Recipe — three tool calls max:
1. Read `docs/PROVENANCE_ENGINE.md` (full file). This is your ONLY read of this file for the entire run.
2. Use `Glob("qws_graph/tests/fixtures/artifacts/**/*")` to discover fixture files. ONE Glob call — no `ls`, no `grep -rl`, no Bash ls.
3. Read only fixture files that could contain graph node/relationship data (skip `.csv` grid/baseline files — those are strategy artifacts, not graph schema). If no fixtures contain graph data, note "no graph fixtures" and move on.
4. Compare any graph-relevant fixture node labels, properties, and relationship types against PROVENANCE_ENGINE schema from step 1.
5. Append findings to story tmp file.

**Do NOT grep PROVENANCE_ENGINE.md. Do NOT `ls` the directory. Do NOT read more than 3 fixture files.**
**Do NOT grep or read test files (tests/unit/, qws_graph/tests/unit/) in this step — test coverage was verified in Step 2b.**

### 2e — Demo seed consistency
Recipe — one Read, no grep:
1. Read `qws_graph/research/graph/cypher.py` (full file — do NOT use limit parameter). This is your ONLY read of this file.
2. Scan MERGE blocks in what you just read: node labels, property names, relationship types.
3. Compare against PROVENANCE_ENGINE schema (already in context from Step 2d).
4. Report mismatches. Append findings to story tmp file.

**Do NOT grep cypher.py. Do NOT re-read it. Do NOT re-read PROVENANCE_ENGINE.md — it is in context from Step 2d.**

**STOP GATE (convention): schema comparison complete → proceed to Step 2f. No further reads, greps, or Bash commands targeting cypher.py, PROVENANCE_ENGINE.md, or store.py. No exceptions.**

### 2f — Cross-story regressions
```
make test-all 2>&1 | tee /tmp/qa_epic_$ARGUMENTS_current.txt
diff /tmp/qa_epic_$ARGUMENTS_baseline.txt /tmp/qa_epic_$ARGUMENTS_current.txt
```
Any `FAILED` line in current not present in baseline → cross-story regression. Flag with story that likely caused it.

## Step 3 — Fix non-lint issues
If fixture or demo seed issues found: fix those directly (these are schema consistency, not lint).
Lint errors are handled by lint-mechanic — do NOT fix them here.

## Step 4 — Commit and push
**ONLY fixture/seed fixes from Step 3 are committed here. Never commit lint changes — `make lint` auto-fixes are NOT authorized for commit. Never use raw `git commit` or `git push` — use `make commit-push-qa` only.**

If fixture/seed fixes were made in Step 3:
```
git add <fixed files by name — never git add -A or git add .>
make commit-push-qa EPIC=$ARGUMENTS
```
If no fixture/seed fixes were made → skip commit entirely, report clean. Do NOT commit lint auto-fixes. Do NOT commit any file not explicitly edited in Step 3.
If only lint fixlist exists → skip commit (lint-mechanic will commit after fixing).

## Step 5 — Teardown, cleanup, and arm gate
```
qw seed --demo --teardown
```
Remove each `/tmp/qa_epic_$ARGUMENTS_<name>.txt` file in separate Bash calls:
```
rm /tmp/qa_epic_$ARGUMENTS_baseline.txt
rm /tmp/qa_epic_$ARGUMENTS_current.txt
rm /tmp/qa_epic_$ARGUMENTS_lint.txt
rm /tmp/qa_epic_$ARGUMENTS_fixlist.txt
rm /tmp/qa_epic_$ARGUMENTS_arrows.txt
rm /tmp/qa_epic_$ARGUMENTS_changed.txt
rm /tmp/qa_epic_$ARGUMENTS_QWS-0601.txt
rm /tmp/qa_epic_$ARGUMENTS_QWS-0602.txt
rm /tmp/qa_epic_$ARGUMENTS_QWS-0603.txt
rm /tmp/qa_epic_$ARGUMENTS_QWS-0604.txt
```
Do NOT use glob patterns or `&&` chains — use separate Bash calls for each rm.

Update agent memory if needed. READ the memory file BEFORE writing to it (Write tool requires prior Read).

After all cleanup and memory writes are done, arm the phase gate:
```
make arm-qa-gate
```

## Step 6 — Report and STOP

**STOP GATE: `make arm-qa-gate` called → output report below and STOP. No further tool calls. No exceptions.**

The phase gate (agent-phase-gate.sh) blocks all tools after `arm-qa-gate` writes `/tmp/agent-qa-epic-done.txt`. The orchestrator reads the report and decides next steps. Do not re-run tests, do not re-read tmp files, do not push.

```
## Epic $ARGUMENTS — QA Report

### Per-story results
| Story | ACs | Unit | Ruff/mypy | Fixtures | Demo seed | Regressions |
|-------|-----|------|-----------|----------|-----------|-------------|

### Lint fixlist
NONE | Written to /tmp/qa_epic_$ARGUMENTS_fixlist.txt (N errors in M files)

### Fixture/seed fixes applied
[list with commit ref, or NONE]

### Outstanding issues
[any unfixed items beyond lint]

### Verdict
CLEAN | LINT_FIXLIST_WRITTEN | ISSUES_REMAINING
```