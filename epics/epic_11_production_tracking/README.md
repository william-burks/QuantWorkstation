# Epic 11 — Production Tracking

## Objective
Track Champion performance in production via MLflow. Split production results from
research results on Champion nodes. Provides browsable promotion-time snapshots and
OOS metric sync after Champions have a live track record.

## Why it exists
Promoted Champions exist only in Neo4j. No external record of IS metrics, hyperparams,
or artifacts exists at promotion time. When a Champion is later degraded to FormerChampion,
the promotion-time snapshot is not independently queryable. MLflow fills this gap —
post-promotion lifecycle only; all pre-promotion provenance stays graph-only.

## Stories

| ID | Name | Status | Blocked On |
|---|---|---|---|
| QWS-1101 | MLflow Champion Registration | READY | ~~QWS-0801 CLOSED~~ (satisfied) |
| QWS-1102 | MLflow OOS Sync | READY | QWS-1101 |

Story files:
- `story_1_mlflow_champion_registration.md`
- `story_2_mlflow_oos_sync.md`

## Entry Condition
After research sessions in Epic 9. Epic 9 provides the first Champion nodes with live
OOS track records that justify the MLflow overhead.

## Dependency Notes
- QWS-1101 first — registers Champion at promotion time.
- QWS-1102 blocked on QWS-1101 — syncs OOS metrics back to the registered MLflow run.
- Epic 11 is independent of Epic 12 (ML Research Layer).

## Done Criteria
- `qw mlflow register <champion_id>` logs IS params, metrics, and artifacts to local MLflow.
- `mlflow_run_id` and `mlflow_experiment_id` written back to Champion node in Neo4j.
- `mlflow_run_id` survives label swap when Champion degrades to FormerChampion.
- `qw mlflow sync-oos <champion_id>` updates the existing MLflow run with live OOS metrics.
- Both story files marked CLOSED.
