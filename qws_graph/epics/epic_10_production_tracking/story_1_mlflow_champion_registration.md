# Story 1 — MLflow Champion Registration

## ID
QWS-1101

## Status
READY

## Blocked On
QWS-0801 CLOSED

## Summary
Register promoted Champions in MLflow at promotion time. New `qw mlflow register <champion_id>`
command reads Champion + Config + Strategy nodes from Neo4j, creates an MLflow experiment and
run, logs params/metrics/artifacts/tags, and writes `mlflow_run_id` + `mlflow_experiment_id`
back to the Champion node. Provides browsable post-promotion Champion history in the MLflow UI
without requiring a persistent server.

## Problem
Promoted Champions exist only in Neo4j. There is no external record of IS metrics, hyperparams,
artifacts, or regime context at the moment of promotion. When a Champion is later degraded to
FormerChampion the promotion-time snapshot is not independently queryable.

## Goal

```zsh
# Register a Champion in MLflow
qw mlflow register champ_abc123

# Browse via MLflow UI (on demand — no persistent server)
mlflow ui
```

## Schema

Two new optional properties on Champion node:

| Property | Type | Default |
|---|---|---|
| `mlflow_run_id` | `str \| null` | `null` |
| `mlflow_experiment_id` | `str \| null` | `null` |

These properties survive the label swap when a Champion is degraded to FormerChampion
(QWS-0801). The ingestion layer must not strip them during `DEGRADED_TO` edge creation.

**No new nodes or edges.**

## In Scope

- `qws_graph/mlflow_integration.py` (new) — `MlflowRegistrar` class:
  - `register(champion_id: str) -> str` returns `mlflow_run_id`
  - Creates experiment named `strategy_id`; run named `champion_id`
  - Logs params: strategy class, all hyperparams, symbol, timeframe, leverage, fees,
    `sl_stop`, `tp_stop`, `time_stop`
  - Logs metrics: `sharpe`, `calmar`, `max_drawdown`, `return`, `profit_factor`,
    `win_rate`, `n_trades` (IS metrics at promotion time)
  - Logs artifacts: equity curve plot (if path exists on disk), trade log CSV (if path
    exists on disk), strategy source file snapshot
  - Logs tags: `champion_id`, `family_id`, regime labels from `IN_REGIME` edges,
    `promotion_date`, `hypothesis_id` (when `TESTED_AS` path traversable from Champion)
  - Writes `mlflow_run_id` and `mlflow_experiment_id` back to Champion node via
    `neo4j_store.set_champion_mlflow_ids()`
- `qws_graph/cli.py` — add `mlflow` subcommand group; `register` subcommand
- `qws_graph/neo4j_store.py` — add `set_champion_mlflow_ids(champion_id, run_id, experiment_id)`
- `tests/unit/test_mlflow_registration.py` (new) — mock MLflow client + mock Neo4j driver;
  no live connections
- `pyproject.toml` — add `mlflow` dependency
- `.gitignore` — add `mlruns/`
- `docs/PROVENANCE_ENGINE.md` — add `mlflow_run_id` + `mlflow_experiment_id` to Champion
  node property table

## Out of Scope

- Persistent MLflow tracking server (local filesystem only; `mlruns/` at repo root)
- OOS metric syncing (QWS-1102)
- Hypothesis lineage, trial history pre-promotion, parameter stability analysis,
  correlation gate results, FormerChampion/RetiredChampion history — graph-only, not MLflow
- Auto-registration at promotion time (explicit `qw mlflow register` only)

**Note:** MLflow owns post-promotion lifecycle only. All pre-promotion provenance
(hypothesis lineage, trial history, parameter stability, correlation gate results) and
all post-degradation history (FormerChampion, RetiredChampion) remain graph-only.

## Repo Touchpoints

- `qws_graph/mlflow_integration.py` (new)
- `qws_graph/cli.py`
- `qws_graph/neo4j_store.py`
- `tests/unit/test_mlflow_registration.py` (new)
- `pyproject.toml`
- `.gitignore`
- `docs/PROVENANCE_ENGINE.md`

## Acceptance Criteria

- [ ] `qw mlflow register <champion_id>` reads Champion, Config, and Strategy nodes from
  Neo4j for the given `champion_id`
- [ ] MLflow experiment is created with name equal to `strategy_id`; run is created with
  name equal to `champion_id`
- [ ] All IS params (strategy class, hyperparams, symbol, timeframe, leverage, fees,
  `sl_stop`, `tp_stop`, `time_stop`) are logged as MLflow params
- [ ] All IS metrics (`sharpe`, `calmar`, `max_drawdown`, `return`, `profit_factor`,
  `win_rate`, `n_trades`) are logged as MLflow metrics
- [ ] Equity curve plot artifact logged when file exists on disk; skipped without error
  when absent
- [ ] Trade log CSV artifact logged when file exists on disk; skipped without error when
  absent
- [ ] Strategy source file snapshot logged as artifact
- [ ] Tags logged: `champion_id`, `family_id`, all regime labels from `IN_REGIME` edges,
  `promotion_date`; `hypothesis_id` logged when `TESTED_AS` path is traversable
- [ ] `mlflow_run_id` and `mlflow_experiment_id` written back to Champion node in Neo4j
  after successful registration
- [ ] Running `qw mlflow register` a second time for the same Champion exits with a clear
  warning (`Champion already registered — mlflow_run_id: <id>`) and does not create a
  duplicate run
- [ ] After a Champion is degraded to FormerChampion (QWS-0801 label swap), `mlflow_run_id`
  and `mlflow_experiment_id` are preserved on the FormerChampion node — verified by
  registering a Champion, degrading it, then querying the FormerChampion node for
  `mlflow_run_id`
- [ ] MLflow backend is local filesystem (`mlruns/` at repo root); no server process required
- [ ] `mlruns/` is listed in `.gitignore`
- [ ] Unit tests mock both MLflow client and Neo4j driver; no live connections

## Definition of Done

- [ ] `MlflowRegistrar` implemented in `qws_graph/mlflow_integration.py`
- [ ] `qw mlflow register` subcommand wired in `qws_graph/cli.py`
- [ ] `set_champion_mlflow_ids()` added to `qws_graph/neo4j_store.py`
- [ ] `mlflow_run_id` + `mlflow_experiment_id` properties documented in
  `docs/PROVENANCE_ENGINE.md` Champion node table
- [ ] `mlflow` added to `pyproject.toml` dependencies
- [ ] `mlruns/` added to `.gitignore`
- [ ] `tests/unit/test_mlflow_registration.py` passes; `ruff check .` and `mypy --strict .`
  clean
- [ ] All affected README files updated
- [ ] Story marked CLOSED

## Date
2026-04-12
