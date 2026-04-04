# qws_graph

Graph V1 sidecar ingestion for QuantWorkstation. `qws_graph` records existing research artifacts into Neo4j without changing current research shell/script entrypoints.

## Purpose and Boundaries

### What this project does now
- Ingests existing artifact outputs (`baseline_csv`, `grid_csv`, `champion_md`, `tracker_md`) into a graph ledger.
- Uses deterministic IDs and idempotent Neo4j writes.
- Supports online persistence and explicit offline queueing.
- Provides `qw record` and `qw reconcile` as the current CLI surface.

### What this project does not do in V1
- No MCP write path.
- No HUD/CodeLens integration.
- No graph-primary workflow state transitions (Epic 3 scope).

Contract source: `qws_graph/docs/graph_v1_contract.md`.

## Architecture and Data Flow

1. Research scripts produce files under `results/` and `research/results/champions/`.
2. Shell hooks call `qw record ... || true` after artifact creation.
3. `qw record` parses and validates artifacts into `ResearchArtifact` payloads.
4. Online mode persists to Neo4j via idempotent MERGE semantics.
5. Offline mode writes validated payloads to `.qws/pending/` and writes receipts.
6. `qw reconcile` reports pending/missing/drift style audit signals.

## Quickstart

### Prerequisites
- Python 3.11+
- Docker with Compose support
- Working directory at repo root (`/Users/will/ClaudeProjects/QuantWorkstation`)

### Neo4j lifecycle (from `qws_graph/`)
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation/qws_graph
make neo4j-up
make neo4j-status
```

### Online ingest example
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv
```

### Offline ingest example
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --offline
```

### Reconcile example
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw reconcile
qw reconcile --json
```

## Command Reference

### `qw record`
Usage:
```text
qw record --file <path> --kind <baseline_csv|grid_csv|champion_md|tracker_md> [options]
```

Current options:
- `--file` (required)
- `--kind` (required)
- `--pivot-from`
- `--offline`
- `--timeout-seconds` (default `3`)
- `--repo-root`
- `--dry-run`

Exit codes:
- `0` success (online persisted or offline queued)
- `1` parse/validation failure
- `2` infrastructure failure (Neo4j unavailable without `--offline`)

### `qw reconcile`
Usage:
```text
qw reconcile [--since <ISO8601>] [--json] [--repo-root <path>]
```

### Neo4j lifecycle commands
From `qws_graph/Makefile`:
- `make neo4j-up`
- `make neo4j-down`
- `make neo4j-restart`
- `make neo4j-logs`
- `make neo4j-status`

## Artifact Naming and Path Requirements

Artifact names must include enough metadata for strategy inference. Current shell-hook runbook pattern:

```text
{instrument}_{direction}_{logic}_{timeframe}_{descriptor}.csv
```

Examples:
- `results/es_bear_sweep_1h_baseline.csv`
- `results/nq_bear_sweep_1h_baseline.csv`
- `results/es_bear_sweep_1h_grid_nypre_v1.csv`

If timeframe is omitted, parsing can fail. See `qws_graph/docs/qws_graph_runbook.md` for the canonical filename convention and shell-entrypoint examples.

## Operational Artifacts

Runtime files are written under repo root `.qws/`:
- `.qws/receipts/*.json`
- `.qws/pending/*.json`
- `.qws/logs/qw.log`

Receipt status values currently used:
- `persisted`
- `pending_offline`

## Closed Story Traceability

This README baseline is derived from all closed Epic 1 story outputs.

| Closed Story | README basis contribution |
| --- | --- |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_0_infra_scaffold_and_docker.md` | Local Neo4j scaffold defaults, env wiring, `qw` entrypoint context |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_1_graph_v1_contract_alignment.md` | Contract-first behavior, artifact kinds, exit code and write semantics alignment |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_2_pydantic_models_and_parsers.md` | Parser/model normalization and validation expectations |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_3_qw_record_cli.md` | `qw record`/`qw reconcile` command surface and mode behavior |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_4_neo4j_idempotent_store.md` | Idempotent MERGE persistence and duplicate-safe re-ingest model |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_5_shell_hooks_receipts_and_reconcile.md` | Shell hook integration with soft-fail behavior and receipt/pending outcomes |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_makefile_neo4j_lifecycle_1.md` | Makefile lifecycle command workflow |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_shell_hook_timing_race.md` | Hook timing safeguard context (`sleep 1` before artifact checks) |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_strategy_artifact_output_paths.md` | Strategy CSV output-path reliability and hook artifact discoverability |

## Next Doc

For operator run steps and troubleshooting, see `qws_graph/docs/qws_graph_runbook.md`.


