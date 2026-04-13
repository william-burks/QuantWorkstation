# Story — Macro Collection Prefect Flow

## ID
QWS-1013

## Status
READY

## Type
infra

## Blocked On
None

## Summary
Add `data/flows/macro.py` Prefect flow that schedules all macro collectors (COT, FRED, EIA, Baker Hughes, Google Trends, BDTI, Economic Calendar, NOAA, USDA, NDVI) and register a deployment in `data/flows/deployment.py`.

## Problem
All Epic 10 and 10b macro collectors run as standalone scripts only. No Prefect scheduling exists for any macro data source — collection requires manual invocation.

## Goal
`data/flows/macro.py` defines a flow that calls each macro collector. `data/flows/deployment.py` registers a `macro-collection` deployment. Runs on same worker as existing flows.

## In Scope
- `data/flows/macro.py` — one flow, calls each collector's `collect()` function
- `data/flows/deployment.py` — add `macro_collection` deployment (daily schedule)
- Unit tests: flow importable, deployment object constructible

## Out of Scope
- Alerting or notification on failure
- Per-collector retry configuration (use global Prefect retry)

## Repo Touchpoints
- `data/flows/macro.py` — new
- `data/flows/deployment.py` — add deployment
- `tests/unit/test_macro_flow.py` — new

## Acceptance Criteria
- [x] `data/flows/macro.py` exists and is importable
- [x] `data/flows/deployment.py` includes `macro_collection` deployment
- [x] `make verify` passes

## Acceptance Test Plan

### AC1: macro.py exists and is importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.flows.macro import macro_collection_flow; print(macro_collection_flow.name)"`
- expect_contains: "macro-collection"
- expect_exit: 0

### AC2: deployment.py includes macro_collection deployment
- type: file_check
- cmd: `grep -c "macro_collection" data/flows/deployment.py`
- expect_contains: "2"
- expect_exit: 0

### AC3: make verify passes
- type: cli
- cmd: `make test 2>&1 | tail -3`
- expect_contains: "passed"
- expect_exit: 0
