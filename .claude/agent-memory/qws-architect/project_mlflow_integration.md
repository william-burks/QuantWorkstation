---
name: MLflow integration architecture
description: Epic 10 Production Tracking — MLflow for post-promotion Champion lifecycle; handoff at explicit register command, not promotion path
type: project
---

MLflow integration is post-promotion only. Neo4j graph owns research phase; MLflow owns production tracking.

**Key decisions (2026-04-11):**
- Handoff: explicit `qw mlflow register <champion_id>`, NOT coupled to promotion path
- Deployment: local filesystem (`mlruns/`), no server process
- OOS sync: same MLflow run, stepped metrics via `qw mlflow sync`
- Schema: `mlflow_run_id` (nullable str) on Champion node — first external system pointer
- Epic 10 — Production Tracking. Two stories: QWS-1101 (registration), QWS-1102 (OOS sync)
- Blocked on QWS-0801 (FormerChampion lifecycle)

**Why:** Champion comparison, artifact browsing, OOS trajectory visualization. Graph can't render UI; MLflow can.

**How to apply:** Any future story touching Champion promotion must NOT add MLflow coupling. Registration stays opt-in. If Champion degrades to FormerChampion, mlflow_run_id must be preserved on the node.
