# Story — Prefect Daemon

## ID
QWS-1100c

## Status
READY

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
- [ ] `~/Library/LaunchAgents/com.quantworkstation.prefect.plist` exists; `launchctl load` succeeds without error
- [ ] Prefect server starts at login; UI accessible at `localhost:4200`
- [ ] All 4 deployments from QWS-1100b visible and triggerable in Prefect UI
- [ ] `prefect.db` present in `.gitignore`
- [ ] `mlruns/` present in `.gitignore`
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] launchd plist load-tested on dev machine
- [ ] All 4 deployments visible and triggerable in Prefect UI
- [ ] Story marked CLOSED
