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

All commands run from the repo root. Neo4j must be running for graph-backed commands.

Exit codes apply to all commands: `0` success, `1` validation/usage error, `2` infrastructure failure.

---

### `qw record`

Ingest a research artifact into Neo4j (or the offline pending queue).

```text
qw record --file <path> --kind <kind> [options]
```

| Flag | Required | Description |
|---|---|---|
| `--file` | yes | Path to artifact file |
| `--kind` | yes | `baseline_csv`, `grid_csv`, `champion_md`, `tracker_md` |
| `--pivot-from` | no | Explicit pivot run_id for champion ingestion |
| `--offline` | no | Skip Neo4j; write validated payload to `.qws/pending/` |
| `--dry-run` | no | Validate only, no write |
| `--source-file` | no | Strategy `.py` source; derives `family_id` from content hash |
| `--all` | no | Bypass significance gate for `grid_csv` (ingest all rows) |
| `--analyze` | no | Run semantic tier analysis (Llama Scout) on `grid_csv` candidates |
| `--timeout-seconds` | no | Neo4j connection timeout, default `3` |
| `--repo-root` | no | Repo root override (auto-detected from git) |

**Examples:**

```zsh
# Ingest a baseline CSV run
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv

# Ingest a grid sweep, keep only significant runs
qw record --file results/es_bear_sweep_1h_grid_v1.csv --kind grid_csv

# Ingest a grid sweep, keep all rows (bypass significance gate)
qw record --file results/es_bear_sweep_1h_grid_v1.csv --kind grid_csv --all

# Ingest a champion markdown with explicit pivot link
qw record \
  --file research/results/futures/liquidity_sweep/cl_bear_liquidity_sweep_1h_golden_champion.md \
  --kind champion_md \
  --pivot-from d2f56cf73a2d

# Ingest a champion with family_id derived from strategy source
qw record \
  --file research/results/futures/liquidity_sweep/cl_bear_liquidity_sweep_1h_golden_champion.md \
  --kind champion_md \
  --source-file strategies/liquidity_sweep/bear_cl_sweep_1h_golden.py

# Validate only, no write
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --dry-run

# Queue for later (Neo4j offline)
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --offline
```

---

### `qw query`

Run a predefined read preset against the graph. Output is NDJSON (one JSON object per line) by default, or wrapped JSON with `--json`.

```text
qw query --name <preset> [--param key=value ...] [--json]
```

**Shortcut:** `--run-history` is an alias for `--name run_history`.

#### Preset reference

| Preset | Required params | Description |
|---|---|---|
| `recent_champions` | — | Most recent champions across all strategies, ordered by freeze date |
| `strategy_lineage` | `strategy_id` | Champion lineage for a single strategy |
| `run_history` | `strategy_id` | All runs for a strategy with timestamp, Sharpe, drawdown, trade count |
| `rank_by_evidence` | `strategy_id` | Runs ranked by `sharpe × √total_trades` — filters lucky streaks from real edge |
| `trace_champion` | `champion_id` | Strategy→Champion lineage for a specific champion |
| `downstream_champions` | `run_id` | Champions that pivoted from a specific run via explicit PIVOTED_FROM edges |
| `cross_artifact_correlation` | `family_id` or `strategy_id` | Strategies in the same family |
| `portfolio_alpha` | — | Aggregate return and Sharpe across all professional/institutional champions |
| `fragility_report` | — | Champions whose fragility list mentions regime sensitivity |
| `staleness_report` | — | Champions frozen more than 30 days ago, ordered by age |
| `instrument_concentration` | — | Champion count and total return aggregated by instrument |
| `pending_offline` | — | Artifacts queued in `.qws/pending/` (no graph connection required) |

**Examples:**

```zsh
# Show most recent champions (default limit 20)
qw query --name recent_champions

# Limit to 5
qw query --name recent_champions --param limit=5

# Champion lineage for a strategy
qw query --name strategy_lineage --param strategy_id=cl-1h-bear-liquidity-sweep

# Run history with timestamps and trade counts
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep

# Same using the shortcut flag
qw query --run-history --param strategy_id=cl-1h-bear-liquidity-sweep

# Rank runs by evidence score (Sharpe × √trades) — primary promotion tool
qw query --name rank_by_evidence --param strategy_id=cl-1h-bear-liquidity-sweep

# Trace a specific champion back to its strategy
qw query --name trace_champion --param champion_id=0555f1cf1766

# Champions that pivoted from a specific run
qw query --name downstream_champions --param run_id=d2f56cf73a2d

# Family correlation by family_id (preferred — direct scan)
qw query --name cross_artifact_correlation --param family_id=a3f1c2b4e5d6

# Family correlation by strategy (resolves family automatically)
qw query --name cross_artifact_correlation --param strategy_id=cl-1h-bear-liquidity-sweep

# Portfolio-level aggregates
qw query --name portfolio_alpha

# Champions with regime sensitivity fragility
qw query --name fragility_report

# Champions frozen more than 30 days ago
qw query --name staleness_report

# Exposure concentration by instrument
qw query --name instrument_concentration

# Pending offline queue (no Neo4j needed)
qw query --name pending_offline

# JSON output (wraps in {"preset": "...", "results": [...]})
qw query --name recent_champions --json

# Pipe NDJSON into jq
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep \
  | jq 'select(.total_trades >= 10) | {run_id, sharpe, total_trades}'
```

---

### `qw abort`

Mark a strategy as ABORTED with a mandatory reason. Writes `Strategy.status`, `Strategy.abort_reason`, `Strategy.aborted_at`.

```text
qw abort --strategy <strategy_id> --reason <text> [--timeout-seconds 3]
```

```zsh
# Abort a strategy after OOS failure
qw abort \
  --strategy cl-1h-bear-liquidity-sweep \
  --reason "OOS Sharpe degraded to 0.8 after regime change — edge not confirmed"

# Abort with a shorter reason
qw abort --strategy es-1h-bear-sweep --reason "Abandoned — superseded by CL sweep"
```

---

### `qw reconcile`

Audit ingested artifacts against graph records. Reports pending files not yet written to Neo4j.

```text
qw reconcile [--since <ISO8601>] [--json] [--repo-root <path>]
```

```zsh
# Text report
qw reconcile

# JSON output
qw reconcile --json

# Filter by ingestion time
qw reconcile --since 2026-04-01T00:00:00Z
```

---

### Neo4j lifecycle (`make` from `qws_graph/`)

```zsh
make neo4j-up        # Start Neo4j container
make neo4j-down      # Stop Neo4j container
make neo4j-restart   # Restart container
make neo4j-status    # Check running state
make neo4j-logs      # Tail container logs
```

---

### Graph integrity QA (`research/bin/qa_graph_integrity.sh`)

Runs 5 structural checks against the live graph: connectivity, flat metrics, fragility report, champion lineage trace, and trade count significance. Exits non-zero on any failure. Prints next recommended action.

```zsh
./research/bin/qa_graph_integrity.sh
```

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


