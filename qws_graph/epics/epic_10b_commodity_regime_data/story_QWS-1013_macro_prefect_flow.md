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
- [ ] `data/flows/macro.py` exists and is importable
- [ ] `data/flows/deployment.py` includes `macro_collection` deployment
- [ ] `make verify` passes
