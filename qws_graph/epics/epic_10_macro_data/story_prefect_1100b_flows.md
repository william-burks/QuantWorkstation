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
Create `data/flows/` directory with crypto, futures, parquet, and deployment flows; configure macOS launchd plist to run Prefect server as a daemon.

## Problem
After scheduler isolation (QWS-1100a), data collection has no scheduler. Epic 10 collectors need retry logic, structured logging, and run history. APScheduler provides none of these.

## Goal
Prefect server runs as a launchd daemon. Crypto, futures, and parquet collection flows are registered with schedules. Each flow retries twice on failure. UI accessible at localhost:4200.

## Design
- Collector modules stay pure — no Prefect imports in `alpaca_crypto.py` or `ibkr_futures.py`
- Flows wrap collectors: import collector functions, decorate with `@flow`/`@task`
- SQLite backend (no Docker, no Postgres)
- `retries=2, retry_delay_seconds=60` on each `@flow`
- launchd plist runs `prefect server start` at login; `RunAtLoad=true`

## In Scope
- `data/flows/__init__.py`, `crypto.py`, `futures.py`, `parquet.py`, `deployment.py`
- macOS launchd plist at `~/Library/LaunchAgents/com.quantworkstation.prefect.plist`
- `.gitignore` entries: `mlruns/`, `prefect.db`
- Schedules: crypto 00:15 UTC, futures 23:20 UTC, parquet 00:30 + 23:35 UTC

## Out of Scope
- Slack/webhook alerting
- Docker or container workers
- Prefect Cloud
- Epic 10 collector flows (added per-story when collectors land)

## Repo Touchpoints
- `data/flows/__init__.py` — new
- `data/flows/crypto.py` — new
- `data/flows/futures.py` — new
- `data/flows/parquet.py` — new
- `data/flows/deployment.py` — new
- `~/Library/LaunchAgents/com.quantworkstation.prefect.plist` — new

## Acceptance Criteria
- [ ] All 5 `data/flows/` files exist and are importable
- [ ] Each flow has `retries=2, retry_delay_seconds=60` on `@flow` decorator
- [ ] Each flow has `@task`-decorated steps for fetch, validate, write
- [ ] `data/collectors/alpaca_crypto.py` and `data/collectors/ibkr_futures.py` have zero Prefect imports
- [ ] `prefect server start` launches cleanly; UI accessible at `localhost:4200`
- [ ] launchd plist exists at `~/Library/LaunchAgents/com.quantworkstation.prefect.plist`; `launchctl load` succeeds
- [ ] `python data/flows/deployment.py` registers all 4 deployments in Prefect UI without error
- [ ] `mlruns/` and `prefect.db` present in `.gitignore`
- [ ] `pytest tests/unit/ -v` passes
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] launchd plist load-tested on dev machine
- [ ] All 4 deployments visible and triggerable in Prefect UI
- [ ] Story marked CLOSED
