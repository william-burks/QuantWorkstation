# qws_graph

Graph V1 sidecar ingestion and read surface for QuantWorkstation. `qws_graph` records existing research artifacts into Neo4j, exposes stable query presets, and provides MCP read-adapter context retrieval without changing research shell/script entrypoints.

## Purpose and Boundaries

### What this project does now
- Ingests artifact outputs (`baseline_csv`, `grid_csv`, `champion_md`, `tracker_md`) into a graph ledger.
- Uses deterministic IDs and idempotent Neo4j writes.
- Supports online persistence and explicit offline queueing.
- Applies grid significance gating with `RunStatsSummary` rollups (`--all` bypass supported).
- Supports semantic curation with optional analyst pass (`--analyze`) writing `Run.curator_note`.
- Supports strategy family tagging from source (`--source-file`) via `Strategy.family_id` derivation.
- Supports operator abort flow via `qw abort` (`Strategy.status`, `Strategy.abort_reason`).
- Exposes query surface via `qw query` presets and stable view functions in `research/graph/query.py`.
- Exposes MCP read context neighborhood retrieval through `research/graph/mcp_adapter.py`.

### What this project does not do in V1
- No MCP write path.
- No HUD/CodeLens integration.
- No graph-primary workflow state transitions (Epic 3 scope).

Contract source: `qws_graph/docs/graph_v1_contract.md`.

## Architecture and Data Flow

1. Research scripts produce files under `results/` and `research/results/champions/`.
2. Shell hooks call `qw record ... || true` after artifact creation.
3. `qw record` parses and validates artifacts into `ResearchArtifact` payloads.
4. Optional grid curation applies significance gate and optional semantic analyst (`--analyze`).
5. Online mode persists to Neo4j via idempotent MERGE semantics.
6. Offline mode writes validated payloads to `.qws/pending/` and writes receipts.
7. `qw query` and MCP adapter run Neo4j-only read projections.
8. `qw reconcile` reports pending/missing/drift style audit signals.

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

### Query example
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name recent_champions --json
```

### Abort example
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw abort --strategy es-1h-bear-sweep --reason "OOS degradation exceeds threshold"
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
- `--source-file`
- `--all`
- `--analyze`

Exit codes:
- `0` success (online persisted or offline queued)
- `1` parse/validation failure
- `2` infrastructure failure (Neo4j unavailable without `--offline`)

### `qw query`
Usage:
```text
qw query --name <preset> [--param key=value ...] [--json]
```

Presets currently implemented:
- `recent_champions`
- `strategy_lineage`
- `run_history`
- `pending_offline`
- `downstream_champions`
- `cross_artifact_correlation`

Exit codes:
- `0` preset ran successfully
- `1` invalid preset name/params
- `2` graph connection required but unavailable

### `qw abort`
Usage:
```text
qw abort --strategy <strategy_id> --reason <text> [--timeout-seconds 3]
```

Exit codes:
- `0` strategy found and marked ABORTED
- `1` validation error or strategy not found
- `2` infrastructure failure

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

## Environment Variables

Graph connection:
- `QW_GRAPH_SCHEME`
- `QW_GRAPH_HOST`
- `QW_GRAPH_PORT`
- `QW_GRAPH_USER`
- `QW_GRAPH_PASSWORD`
- `QW_GRAPH_DATABASE`

Semantic tier:
- `QW_AI_ANALYST_ENDPOINT` (required for `--analyze` path)
- `QW_AI_ANALYST_MODEL` (default: `Llama-4-Scout-17B-16E-Instruct`)
- `QW_AI_PROVIDER` (default: `llama`)

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

This README baseline is derived from closed stories in both complete epic directories.

| Closed Story | README basis contribution |
| --- | --- |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_0_infra_scaffold_and_docker.md` | Local Neo4j scaffold defaults, env wiring, `qw` entrypoint context |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_1_graph_v1_contract_alignment.md` | Contract-first behavior, artifact kinds, exit code and write semantics alignment |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_2_pydantic_models_and_parsers.md` | Parser/model normalization and validation expectations |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_3_qw_record_cli.md` | `qw record`/`qw reconcile` baseline command surface |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_4_neo4j_idempotent_store.md` | Idempotent MERGE persistence and duplicate-safe re-ingest model |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_5_shell_hooks_receipts_and_reconcile.md` | Shell hook integration with soft-fail behavior and receipt/pending outcomes |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_6_readme_and_runbook_basis.md` | Epic 1 documentation baseline and operator framing |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_baseline_csv_validation_regression.md` | CSV validation hardening reflected in operator expectations |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_makefile_neo4j_lifecycle_1.md` | Makefile lifecycle command workflow |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_shell_hook_timing_race.md` | Hook timing safeguard context (`sleep 1` before artifact checks) |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_strategy_artifact_output_paths.md` | Strategy CSV output-path reliability and hook artifact discoverability |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/spike_lean_neighborhood_optimization.md` | Lean-neighborhood read-model direction and bounded retrieval rationale |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_0_target_state_schema_mapping.md` | Canonical read-shape mapping constraints |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_1_read_models_and_query_projections.md` | Query projections and DTO-backed read surfaces |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_2_qw_query_presets.md` | `qw query` preset routing and validation conventions |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_3_mcp_read_tool_contract.md` | MCP read adapter contract and graph-only read policy |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_4_lineage_and_pivot_queries.md` | Explicit pivot lineage and cross-artifact query paths |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_docs_sync_epic2.md` | Epic 2 docs synchronization and command/read surface updates |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_family_definitions_significance_filtering.md` | Family-aware significance filtering semantics |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_family_id_backfill_migration.md` | `family_id` backfill and migration behavior |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_semantic_gate_llama4.md` | Semantic tier (`--analyze`) and `Run.curator_note` behavior |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_strategy_family_definitions.md` | Strategy-family taxonomy framing and correlation quality target |

## Next Doc

For operator run steps and troubleshooting, see `qws_graph/docs/qws_graph_runbook.md`.


