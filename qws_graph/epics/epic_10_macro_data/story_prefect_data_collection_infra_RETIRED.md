RETIRED — split into QWS-1100a and QWS-1100b.

# Story — Prefect Data Collection Infrastructure

## ID
QWS-1100

## Status
DRAFT

## Date
2026-04-12

## Summary
Replace APScheduler for all data collection jobs with Prefect flows. Rename
`execution/scheduler.py` to `execution/risk_scheduler.py` (retains only the 2
latency-sensitive risk jobs). Introduce `data/flows/` directory with crypto,
futures, and parquet flows. Run Prefect server as a macOS launchd daemon.

## Problem
Data collection jobs (crypto, futures, parquet export) are bundled with
execution risk jobs in `execution/scheduler.py`. This conflates latency-sensitive
risk heartbeats with batch overnight collectors that benefit from retries,
structured logging, and a UI. As Epic 10 collectors land they need a scheduler
that supports retries and observability without touching risk job timing.

## Goal
Establish Prefect as the standard scheduler for all data collection workloads.
Isolate risk jobs into a separate module. Give collectors retry behavior and
visibility into past runs without adding operational complexity (SQLite backend,
no Docker, no Postgres).

## Deliverable
- `execution/risk_scheduler.py` — renamed from `execution/scheduler.py`; retains
  only `risk_heartbeat` (60s) and `risk_day_reset` (00:00 UTC) APScheduler jobs
- `data/flows/__init__.py`
- `data/flows/crypto.py` — `@flow` wrapping `alpaca_crypto.collect_all()`, scheduled 00:15 UTC daily
- `data/flows/futures.py` — `@flow` wrapping `ibkr_futures.collect_all_timeframes()`, scheduled 23:20 UTC daily
- `data/flows/parquet.py` — `@flow` wrapping existing parquet export logic, scheduled 00:30 + 23:35 UTC daily
- `data/flows/deployment.py` — schedule definitions (serves as `prefect.yaml` alternative)
- macOS launchd plist for `prefect server start` (background daemon, persists across reboots)
- `prefect` added to `pyproject.toml` dependencies
- `.gitignore` updated: `mlruns/` and `prefect.db` added

## In Scope
- `execution/scheduler.py` → `execution/risk_scheduler.py` rename; remove all collection jobs from it
- `data/flows/` directory with crypto, futures, parquet flows
- Prefect server via launchd (SQLite backend, default local process work pool)
- `retries=2, retry_delay_seconds=60` on each `@flow` decorator
- Prefect `@task` for each logical step: fetch, validate, write
- Inline validation stub pattern (see Implementation Notes)
- `.gitignore` entries for `mlruns/` and `prefect.db`
- Update all internal imports that reference `execution/scheduler` to `execution/risk_scheduler`

## Out of Scope
- Slack/webhook alerting on flow failure (future story)
- Docker or container-based workers
- Postgres backend (SQLite is sufficient)
- Prefect Cloud — local server only
- `validate_bars()` implementation body (lands in QWS-1010; stub raises `NotImplementedError`)

## Implementation Notes

### Collector modules stay pure
Collector modules (`alpaca_crypto.py`, `ibkr_futures.py`) must not import or
depend on Prefect. Flows import from collectors and wrap them. This preserves
CLI invocability and keeps unit tests free of Prefect fixtures.

### Flow skeleton pattern
```python
from prefect import flow, task
from data.collectors.alpaca_crypto import collect_all

@task
def fetch_crypto():
    return collect_all()

@task
def validate(df, freq: str):
    # QWS-1010 fills this in; stub acceptable until then
    pass

@task
def write_crypto(df):
    # calls store.write_bars() — no direct lib writes
    ...

@flow(name="collect-crypto", retries=2, retry_delay_seconds=60)
def collect_crypto_flow():
    df = fetch_crypto()
    validate(df, freq="1H")
    write_crypto(df)
```

### Inline validation stub pattern (for QWS-1010 handoff)
When QWS-1010 (Data Quality Validation) lands, `validate_bars(df, freq)` raises
on P1 failures (OHLCV violations, NaN, duplicates, non-UTC). The `validate` task
calls `validate_bars` — no flow changes needed, just fill in the function body.

### deployment.py schedule example
```python
from prefect import serve
from data.flows.crypto import collect_crypto_flow
from data.flows.futures import collect_futures_flow
from data.flows.parquet import export_parquet_flow

if __name__ == "__main__":
    serve(
        collect_crypto_flow.to_deployment(name="crypto-daily", cron="15 0 * * *"),
        collect_futures_flow.to_deployment(name="futures-daily", cron="20 23 * * *"),
        export_parquet_flow.to_deployment(name="parquet-post-crypto", cron="30 0 * * *"),
        export_parquet_flow.to_deployment(name="parquet-post-futures", cron="35 23 * * *"),
    )
```

### launchd plist location
`~/Library/LaunchAgents/com.quantworkstation.prefect.plist` — runs
`prefect server start` as the current user on login; `RunAtLoad=true`.

### risk_scheduler.py scope after rename
Only these 2 jobs remain — do not add collection jobs back:
- `risk_heartbeat` — 60s interval, APScheduler
- `risk_day_reset` — 00:00 UTC cron, APScheduler

### Epic 10 collectors
Stories QWS-1001–1010 can run as plain scripts before this story closes. When
QWS-1100 is CLOSED, each new collector SHOULD add a corresponding flow in
`data/flows/` rather than registering a new APScheduler job. This is a soft
convention, not enforced at merge time.

## Acceptance Criteria
- [ ] `execution/risk_scheduler.py` exists; contains only `risk_heartbeat` and `risk_day_reset` APScheduler jobs
- [ ] `execution/scheduler.py` deleted; no remaining imports of it anywhere in the codebase
- [ ] `data/flows/__init__.py`, `crypto.py`, `futures.py`, `parquet.py`, `deployment.py` all exist
- [ ] Each flow has `retries=2, retry_delay_seconds=60` on `@flow` decorator
- [ ] Each flow has `@task`-decorated steps for fetch, validate, write
- [ ] `data/collectors/alpaca_crypto.py` and `data/collectors/ibkr_futures.py` have zero Prefect imports
- [ ] `python -m data.collectors.alpaca_crypto` and `python -m data.collectors.ibkr_futures` still callable without Prefect installed
- [ ] `prefect server start` launches cleanly; UI accessible at `localhost:4200`
- [ ] launchd plist exists at `~/Library/LaunchAgents/com.quantworkstation.prefect.plist`; `launchctl load` succeeds
- [ ] `python data/flows/deployment.py` registers all 4 deployments in Prefect UI without error
- [ ] `mlruns/` and `prefect.db` present in `.gitignore`
- [ ] `pytest tests/unit/ -v` passes (collector tests unaffected by Prefect wrapping)
- [ ] `make verify` passes

## Definition of Done
- [ ] `execution/risk_scheduler.py` merged; `execution/scheduler.py` deleted
- [ ] `data/flows/` directory merged with all 5 files
- [ ] launchd plist committed and load-tested on dev machine
- [ ] All 4 deployments visible and triggerable in Prefect UI
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on: nothing
- Soft prerequisite for: QWS-1001–1010 (Epic 10 collectors should adopt `data/flows/` pattern when available)
- Enables: structured retry + run history for all data collection without touching risk job timing
