---
name: Prefect scheduling architecture
description: Decision to adopt Prefect for data collection only; APScheduler retained for execution/risk; inline validation pattern; data/flows/ directory
type: project
---

Prefect replaces APScheduler for data collection jobs only. Execution/risk jobs (heartbeat, day_reset) stay on APScheduler in `execution/risk_scheduler.py`.

**Why:** Epic 10 adds 10+ collectors with real dependency chains (validation must follow collection, calendar before research). APScheduler has no dependency DAG, retry visibility, or UI. But execution heartbeat (60s) is latency-sensitive — Prefect task overhead inappropriate there.

**How to apply:**
- All new collector stories (QWS-1001–1010) should create Prefect flows in `data/flows/`
- QWS-1010 (validation) delivers `validate_bars()` as inline Prefect task, not standalone flow
- Prefect server runs locally via launchd, SQLite backend, UI at localhost:4200
- Story QWS-1100 delivers infra + migration of existing 3 data jobs
- Epic 10 collectors soft-depend on QWS-1100 (can run as scripts without Prefect)
- No new epic needed — QWS-1100 goes in Backlog section
