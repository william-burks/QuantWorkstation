# Story — Scheduler Isolation

## ID
QWS-1100a

## Status
READY

## Type
infra

## Blocked On
None

## Summary
Rename `execution/scheduler.py` to `execution/risk_scheduler.py`, strip all collection jobs from it (keep only `risk_heartbeat` and `risk_day_reset`), update all imports, and add `prefect` to `pyproject.toml`.

## Problem
Data collection jobs and latency-sensitive risk jobs share `execution/scheduler.py`. Separating them is a prerequisite for Prefect flows (QWS-1100b) — Prefect must not touch risk job timing.

## Goal
`execution/risk_scheduler.py` exists and contains only the 2 risk jobs. No other module imports the old path. `prefect` is in `pyproject.toml` ready for QWS-1100b.

## Design
- Rename file; keep `risk_heartbeat` (60s APScheduler) and `risk_day_reset` (00:00 UTC APScheduler) intact
- Remove any collection job registrations (crypto, futures, parquet) from the file
- Update all `from execution.scheduler import ...` and `from execution import scheduler` references codebase-wide
- Add `prefect` to `[project.dependencies]` in `pyproject.toml`

## In Scope
- File rename and job removal
- Import updates across codebase
- `prefect` added to `pyproject.toml`

## Out of Scope
- Prefect flows (QWS-1100b)
- Any changes to risk job logic or timing

## Repo Touchpoints
- `execution/risk_scheduler.py` — new (renamed from `execution/scheduler.py`)
- `execution/scheduler.py` — deleted
- `pyproject.toml` — add `prefect` to dependencies

## Acceptance Criteria
- [x] `execution/risk_scheduler.py` exists and contains only `risk_heartbeat` and `risk_day_reset` APScheduler jobs
- [x] `execution/scheduler.py` deleted; no remaining imports of it anywhere in codebase
- [x] `prefect` present in `pyproject.toml` dependencies
- [x] `pytest tests/unit/ -v` passes
- [x] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: risk_scheduler.py exists with only 2 risk jobs
- type: file_check
- cmd: `python -c "import ast, sys; tree = ast.parse(open('execution/risk_scheduler.py').read()); fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; sys.exit(0 if 'job_risk_heartbeat' in fns and 'job_risk_day_reset' in fns and 'job_collect_crypto' not in fns and 'job_collect_futures' not in fns else 1)"`
- expect_exit: 0

### AC2: scheduler.py deleted and no imports remain
- type: file_check
- cmd: `python -c "import os, subprocess, sys; e = not os.path.exists('execution/scheduler.py'); r = subprocess.run(['grep', '-r', 'execution.scheduler', '.', '--include=*.py', '--exclude-dir=.venv'], capture_output=True).returncode; sys.exit(0 if e and r != 0 else 1)"`
- expect_exit: 0

### AC3: prefect in pyproject.toml
- type: file_check
- cmd: `grep -q 'prefect' pyproject.toml`
- expect_exit: 0

### AC4: unit tests pass
- type: cli
- cmd: `make test 2>&1 | tail -3`
- expect_contains: "633 passed"

### AC5: typecheck clean
- type: cli
- cmd: `make typecheck 2>&1 | tail -2`
- expect_contains: "no issues found"
