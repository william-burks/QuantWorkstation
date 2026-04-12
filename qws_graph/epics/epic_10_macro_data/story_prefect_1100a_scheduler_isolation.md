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
- [ ] `execution/risk_scheduler.py` exists and contains only `risk_heartbeat` and `risk_day_reset` APScheduler jobs
- [ ] `execution/scheduler.py` deleted; no remaining imports of it anywhere in codebase
- [ ] `prefect` present in `pyproject.toml` dependencies
- [ ] `pytest tests/unit/ -v` passes
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Story marked CLOSED
