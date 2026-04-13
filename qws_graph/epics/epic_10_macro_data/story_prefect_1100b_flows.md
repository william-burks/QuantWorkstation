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
- [ ] All 5 `data/flows/` files exist and are importable (`python -c "import data.flows"` succeeds)
- [ ] `@flow(retries=2, retry_delay_seconds=60)` present on all collection flows
- [ ] Each collector step wrapped as a `@task`
- [ ] Zero Prefect imports in `data/collectors/alpaca_crypto.py` or `data/collectors/ibkr_futures.py`
- [ ] `python data/flows/deployment.py` registers 4 deployments successfully when Prefect server is running
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Flows importable without Prefect server running
- [ ] 4 deployments register when server is running
- [ ] Story marked CLOSED
