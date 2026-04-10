Run unit tests and static analysis for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Note which Python files the story touched.

## Step 2 — Run unit tests
```
pytest tests/unit/ -v 2>&1
```
Record: passed, failed, errored, skipped.

If any test fails:
1. Read failing test and code it exercises
2. If test bug (wrong expectation after legitimate schema change) — fix test
3. If code bug — fix code
4. Re-run until clean
Report every fix made.

## Step 3 — Ruff + mypy on touched files
```
ruff check <files> && mypy --strict <files> 2>&1
```
Fix all warnings before continuing.

## Step 4 — Stage fixed files
```
git add <test files fixed>
git add <source files fixed>
```
Never `git add -A` or `git add .`.

## Step 5 — Report
```
## $ARGUMENTS — Unit Test Report

### pytest
- Passed: X | Failed: Y | Errored: Z | Skipped: W

### ruff / mypy
- clean | <issues fixed>

### Fixes made
- <file>: <what changed>
```
