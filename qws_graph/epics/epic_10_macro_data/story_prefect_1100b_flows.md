# Story — Prefect Flows

## ID
QWS-1100b

## Status
BLOCKED

## Type
infra

## Blocked On
QWS-1100a

## Summary
Create all `data/flows/` Python files — crypto, futures, parquet, and deployment — wiring existing collectors into Prefect `@task`/`@flow` decorators with retry config and schedule registration. Collectors gain no direct Prefect imports. Daemon setup deferred to QWS-1100c.

## Problem
Collectors run manually only. No scheduling, no retry, no deployment registry. Flows layer isolates Prefect from collectors so collectors remain importable without Prefect installed.

## Goal
Five new `data/flows/` files exist, are importable, register 4 deployments against a running Prefect server, and pass `make verify`.

## In Scope
- `data/flows/__init__.py` — new
- `data/flows/crypto.py` — new; wraps `alpaca_crypto` collector; `retries=2, retry_delay_seconds=60`
- `data/flows/futures.py` — new; wraps `ibkr_futures` collector; `retries=2, retry_delay_seconds=60`
- `data/flows/parquet.py` — new; parquet export flow; `retries=2, retry_delay_seconds=60`
- `data/flows/deployment.py` — new; registers all 4 deployments with schedules via `flow.serve()` or `Deployment.build_from_flow()`
- Retry config: `retries=2, retry_delay_seconds=60` on all `@flow` decorators
- Schedule registration: deployment registration runnable via `python data/flows/deployment.py`

## Out of Scope
- macOS launchd plist (QWS-1100c)
- `.gitignore` entries for `prefect.db` and `mlruns/` (QWS-1100c)
- `mlruns/` gitignore entry (Epic 11 — not in scope here)
- Slack/webhook alerting
- Docker or container workers
- Prefect Cloud

## Repo Touchpoints
- `data/flows/__init__.py` — new
- `data/flows/crypto.py` — new
- `data/flows/futures.py` — new
- `data/flows/parquet.py` — new
- `data/flows/deployment.py` — new

## Acceptance Criteria
- [x] All 5 `data/flows/` files exist and are importable (`python -c "import data.flows"` succeeds)
- [x] `@flow(retries=2, retry_delay_seconds=60)` present on all collection flows
- [x] Each collector step wrapped as a `@task`
- [x] Zero Prefect imports in `data/collectors/alpaca_crypto.py` or `data/collectors/ibkr_futures.py`
- [x] `python data/flows/deployment.py` registers 4 deployments successfully when Prefect server is running
- [x] `make verify` passes

## Definition of Done
- [x] All ACs passing
- [x] Flows importable without Prefect server running
- [x] 4 deployments register when server is running
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: All 5 files exist and are importable
- type: file_check
- cmd: `/Users/will/ClaudeProjects/QuantWorkstation/.venv/bin/python -c "import data.flows; import data.flows.crypto; import data.flows.futures; import data.flows.parquet; import data.flows.deployment; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC2: @flow retries=2 on all collection flows
- type: file_check
- cmd: `grep -c "retries=2, retry_delay_seconds=60" data/flows/crypto.py data/flows/futures.py data/flows/parquet.py`
- expect_contains: "1"
- expect_exit: 0

### AC3: Each collector step wrapped as @task
- type: file_check
- cmd: `grep -l "@task" data/flows/crypto.py data/flows/futures.py data/flows/parquet.py`
- expect_contains: "crypto.py"
- expect_exit: 0

### AC4: Zero Prefect imports in collectors
- type: file_check
- cmd: `grep -L "prefect" data/collectors/alpaca_crypto.py data/collectors/ibkr_futures.py`
- expect_contains: "alpaca_crypto.py"
- expect_exit: 0

### AC5: deployment.py defines 4 deployment registrations
- type: file_check
- cmd: `grep -c "build_from_flow\|\.serve(" data/flows/deployment.py`
- expect_contains: "4"
- expect_exit: 0

### AC6: make verify passes
- type: cli
- cmd: `make -C /Users/will/ClaudeProjects/QuantWorkstation test 2>&1 | tail -3`
- expect_contains: "passed"
- expect_exit: 0
