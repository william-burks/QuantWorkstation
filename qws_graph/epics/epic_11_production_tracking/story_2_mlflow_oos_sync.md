# Story 2 — MLflow OOS Sync

## ID
QWS-1102

## Status
READY

## Blocked On
QWS-1101 CLOSED

## Summary
Sync OOS metrics from Neo4j Champion node to an existing MLflow run. New `qw mlflow sync
<champion_id>` command reads current OOS state from the Champion node and logs metrics as
a stepped series to the run registered in QWS-1101. Idempotent. Does not modify the
`qw record --oos` path.

## Problem
After a Champion is registered in MLflow (QWS-1101), OOS performance updates accumulate in
Neo4j only. The MLflow run has a snapshot of IS metrics at promotion time but no ongoing
OOS record. There is no way to view OOS performance history in the MLflow UI or detect
degradation trends without querying Neo4j directly.

## Goal

```zsh
# Sync current OOS state to MLflow (run `qw record --oos` first as normal)
qw mlflow sync champ_abc123

# Re-run is a no-op for the same OOS period — safe to run repeatedly
qw mlflow sync champ_abc123
```

## Schema

No new nodes, edges, or properties. Reads existing OOS properties from Champion node:
`oos_status`, `oos_date`, `metrics_oos_sharpe`. No schema changes.

## In Scope

- `qws_graph/mlflow_integration.py` — add `MlflowSyncer` class (or extend
  `MlflowRegistrar`):
  - `sync(champion_id: str) -> None`
  - Reads `oos_status`, `oos_date`, `metrics_oos_sharpe` from Champion node in Neo4j
  - Logs OOS metrics as stepped MLflow metrics (step = OOS update count, derived from
    existing records on the run)
  - Updates `oos_status` and `oos_date` as tags on the MLflow run
  - Idempotent: re-running sync for the same `oos_date` is a no-op (checks existing
    step tags before logging)
  - If Champion has no `mlflow_run_id`: prints
    `WARNING: Champion <id> has no mlflow_run_id — register first with: qw mlflow register <id>`
    and exits cleanly with code 0; does NOT auto-register
- `qws_graph/cli.py` — add `sync` subcommand under existing `mlflow` group
- `tests/unit/test_mlflow_oos_sync.py` (new) — mock MLflow client + mock Neo4j driver;
  no live connections; covers idempotency (same OOS period → no duplicate step),
  missing `mlflow_run_id` warning path

## Out of Scope

- Modifying `qw record --oos` (existing path unchanged)
- Auto-sync on `qw record --oos` (sync remains an explicit separate command)
- Syncing pre-promotion metrics (IS-only metrics already logged at registration)
- Hypothesis lineage, trial history pre-promotion, parameter stability analysis,
  correlation gate results, FormerChampion/RetiredChampion history — graph-only, not MLflow

**Note:** MLflow owns post-promotion lifecycle only. All pre-promotion provenance
(hypothesis lineage, trial history, parameter stability, correlation gate results) and
all post-degradation history (FormerChampion, RetiredChampion) remain graph-only.

## Repo Touchpoints

- `qws_graph/mlflow_integration.py`
- `qws_graph/cli.py`
- `tests/unit/test_mlflow_oos_sync.py` (new)

## Acceptance Criteria

- [ ] `qw mlflow sync <champion_id>` reads `oos_status`, `oos_date`, and
  `metrics_oos_sharpe` from the Champion node in Neo4j
- [ ] OOS metrics are logged to the existing MLflow run as stepped metrics; step
  increments with each new OOS period
- [ ] `oos_status` and `oos_date` are updated as tags on the MLflow run after sync
- [ ] Running `qw mlflow sync` twice for the same `oos_date` is a no-op — no duplicate
  step is written; exit code 0
- [ ] If Champion node has `mlflow_run_id = null` (never registered), prints
  `WARNING: Champion <id> has no mlflow_run_id — register first with: qw mlflow register <id>`
  and exits cleanly with code 0 without calling MLflow
- [ ] `qw record --oos` behavior is unchanged — OOS sync to MLflow is a separate
  explicit command
- [ ] Unit tests mock both MLflow client and Neo4j driver; no live connections
- [ ] Idempotency test: sync called twice with same `oos_date` → MLflow client logs
  metric exactly once

## Definition of Done

- [ ] `sync()` implemented in `qws_graph/mlflow_integration.py`
- [ ] `qw mlflow sync` subcommand wired in `qws_graph/cli.py`
- [ ] `tests/unit/test_mlflow_oos_sync.py` passes; `ruff check .` and `mypy --strict .`
  clean
- [ ] All affected README files updated
- [ ] Story marked CLOSED

## Date
2026-04-12
