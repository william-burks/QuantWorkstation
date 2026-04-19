# Story — Prefect Daemon

## ID
QWS-1100c

## Status
CLOSED

## Type
infra

## Blocked On
QWS-1100b

## Summary
Configure macOS launchd to run Prefect server as a login daemon and add `.gitignore` entries for Prefect and MLflow artifacts. Flows registered in QWS-1100b become permanently scheduled after this story closes.

## Problem
After QWS-1100b, flows exist but require manual `prefect server start`. Without a daemon, collection stops on reboot. `.gitignore` entries for `prefect.db` and `mlruns/` are also deferred here to keep 1100b focused on Python deliverables.

## Goal
Prefect server starts automatically at login. All 4 deployments from QWS-1100b are visible and triggerable in the Prefect UI at localhost:4200. `prefect.db` and `mlruns/` excluded from git.

## In Scope
- macOS launchd plist at `~/Library/LaunchAgents/com.quantworkstation.prefect.plist`; `RunAtLoad=true`; runs `prefect server start`
- `.gitignore` entries: `prefect.db`, `mlruns/`
- Verify all 4 QWS-1100b deployments visible and triggerable in Prefect UI after daemon start

## Out of Scope
- New flows (covered by QWS-1100b and future collector stories)
- Slack/webhook alerting
- Docker or container workers
- Prefect Cloud

## Repo Touchpoints
- `~/Library/LaunchAgents/com.quantworkstation.prefect.plist` — new (outside repo; document install step in story)
- `.gitignore` — add `prefect.db` and `mlruns/`

## Acceptance Criteria
- [x] `~/Library/LaunchAgents/com.quantworkstation.prefect.plist` exists; `launchctl load` succeeds without error — manual — requires running Prefect server
- [x] Prefect server starts at login; UI accessible at `localhost:4200` — manual — requires running Prefect server
- [x] All 4 deployments from QWS-1100b visible and triggerable in Prefect UI — manual — requires running Prefect server
- [x] `prefect.db` present in `.gitignore`
- [x] `mlruns/` present in `.gitignore`
- [x] `make verify` passes

## Definition of Done
- [x] All ACs passing
- [x] launchd plist load-tested on dev machine
- [x] All 4 deployments visible and triggerable in Prefect UI
- [x] Story marked CLOSED
