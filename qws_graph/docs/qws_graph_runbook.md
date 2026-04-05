# qws_graph Runbook

Operator runbook for Graph V1 as currently implemented in QuantWorkstation.

## Intended Behavior Now

- Existing research scripts remain the execution entrypoints.
- Graph ingestion is post-run and soft-fail (`qw record ... || true`).
- Online mode writes to Neo4j and receipts.
- Offline mode writes to pending queue and receipts with `pending_offline` status.
- Re-ingest is idempotent by deterministic IDs and MERGE semantics.
- Grid artifacts can be curated by significance gate unless `--all` is passed.
- Optional semantic tier (`--analyze`) can annotate selected runs with `curator_note`.
- Query presets and MCP adapter read only from graph projections (no file fallback).
- `qw abort` can mark a strategy as ABORTED with an explicit reason.

Primary references:
- `qws_graph/docs/graph_v1_contract.md`

## Day-0 Setup and Verification

### 1) Start local Neo4j
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation/qws_graph
make neo4j-up
make neo4j-status
```

Expected:
- `qws-neo4j` service is up.
- Neo4j Browser reachable at `http://localhost:7474`.

### 2) Verify CLI availability
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --help
qw reconcile --help
qw query --help
qw abort --help
```

Expected:
- `qw record` shows required `--file`, `--kind` and current options.
- `qw reconcile` shows `--since`, `--json`, `--repo-root`.
- `qw query` lists available presets.
- `qw abort` shows `--strategy` and `--reason`.

## Day-1 Operations

### Activate Python environment
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Online ingestion path
Use this when Neo4j is up and reachable.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/bear_es_sweep_1h_baseline.py
```

Expected:
- Exit `0` on success.
- Receipt written to `.qws/receipts/<id>.json` with `status: persisted`.

### Offline ingestion path
Use this when Neo4j is intentionally disabled or unavailable.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/bear_es_sweep_1h_baseline.py --offline
```

Expected:
- Exit `0` on success.
- Pending payload in `.qws/pending/<id>.json`.
- Receipt in `.qws/receipts/<id>.json` with `status: pending_offline`.

### Ingestion with strategy family source binding
Use this when you want deterministic `Strategy.family_id` derived from source content.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record \
  --file results/es_bear_sweep_1h_grid_nypre_v1.csv \
  --kind grid_csv \
  --source-file strategies/rsi_reversion.py
```

Expected:
- Ingest succeeds with normal `qw record` exit semantics.
- Strategy node includes `family_id` for downstream correlation filtering.

### Ingestion with semantic tier (`--analyze`)
Use this when LLM-assisted curation is desired for grid artifacts.

Prerequisite environment:
```zsh
export QW_AI_PROVIDER=llama
export QW_AI_ANALYST_ENDPOINT=http://localhost:5001
export QW_AI_ANALYST_MODEL=Llama-4-Scout-17B-16E-Instruct
```

Run:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record \
  --file results/es_bear_sweep_1h_grid_nypre_v1.csv \
  --kind grid_csv \
  --analyze
```

Expected:
- If analyst endpoint is reachable, selected runs may include `curator_note` values.
- If analyst endpoint is unavailable, CLI logs warning and falls back to math tier.

### Abort a strategy family
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw abort --strategy es-1h-bear-sweep --reason "OOS degradation exceeds threshold"
```

Expected:
- Exit `0` when strategy exists and is marked ABORTED.
- Exit `1` when strategy is not found or reason is empty.

### Query presets (`qw query`)

Recent champions:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name recent_champions --param limit=10 --json
```

Strategy lineage:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name strategy_lineage --param strategy_id=es-1h-bear-sweep --json
```

Run history:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name run_history --param strategy_id=es-1h-bear-sweep --json
```

Pending offline queue:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name pending_offline --json
```

Downstream champions from explicit pivots:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name downstream_champions --param run_id=a1b2c3d4e5f6 --json
```

Cross-artifact correlation:
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw query --name cross_artifact_correlation --param strategy_id=es-1h-bear-sweep --json
```

### Shell entrypoint behavior
Current hook behavior in the two scripts:
- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`

Hook guarantees:
1. `sleep 1` before artifact existence checks to reduce flush race risk.
2. Missing artifact logs warning and continues.
3. `QW_GRAPH_ENABLED=false` routes to `qw record ... --offline || true`.
4. Otherwise runs `qw record ... || true`.
5. Hook failures do not stop script execution.

### How to run the shell entrypoints

#### Baseline shell run with graph enabled
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true zsh research/run_es_nq_bear_sweep_1h_baseline.sh
```

#### Phase 2 shell run with graph disabled (offline queue)
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/run_es_phase2.sh 1a
```

#### Phase 2 shell run to verify warning/retry visibility
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true QW_GRAPH_PORT=1 zsh research/run_es_phase2.sh 1a
```

### Shell artifact filename convention

Artifact filenames must encode strategy metadata for parser inference:

```text
{instrument}_{direction}_{logic}_{timeframe}_{descriptor}.csv
```

Examples:
- `results/es_bear_sweep_1h_baseline.csv`
- `results/nq_bear_sweep_1h_baseline.csv`
- `results/es_bear_sweep_1h_nypre.csv`
- `results/es_bear_sweep_1h_grid_nypre_v1.csv`

## Receipt and Pending Queue Operations

### Inspect receipt output
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
ls -la .qws/receipts
```

### Inspect pending queue
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
ls -la .qws/pending
```

### Reconcile queue and drift indicators
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw reconcile
qw reconcile --json
```

## Failure Modes and Operator Responses

| Failure mode | Signal | Response |
| --- | --- | --- |
| Neo4j unavailable in online mode | `WARNING: Neo4j unavailable (timeout after 3s)` + `INFO` guidance | Start Neo4j (`make neo4j-up`) or rerun with `--offline`. |
| Validation failure | `ERROR: Validation failed: ...` and exit `1` | Fix artifact content or naming; rerun `qw record`. |
| Semantic tier unavailable | `WARNING: AI analyst unavailable — ...` | Verify `QW_AI_ANALYST_ENDPOINT` and local analyst service; rerun with `--analyze` or proceed with fallback tier. |
| Abort target missing | `ERROR: Strategy '...' not found in graph` | Confirm `strategy_id` exists via `qw query` and retry with correct ID. |
| Missing artifact in shell hook | Script warns artifact missing and continues | Confirm strategy script wrote expected path; rerun script after fixing path/name. |
| Receipt write failure | `ERROR: Failed to write receipt: ...` | Check permissions/path under `.qws/receipts`; rerun command. |
| Pending write failure in offline mode | `ERROR: Failed to write pending payload: ...` | Check `.qws/pending` permissions and disk state; rerun. |

## Verification Checklist (Current Intended Workflow)

- [ ] Neo4j lifecycle commands run via `qws_graph/Makefile`.
- [ ] `qw record` online path writes `status: persisted` receipt.
- [ ] `qw record --offline` writes pending + `status: pending_offline` receipt.
- [ ] `qw record --source-file` sets strategy family lineage metadata.
- [ ] `qw record --analyze` runs semantic tier when endpoint is available and falls back when unavailable.
- [ ] Shell scripts complete even if ingestion fails (`|| true`).
- [ ] `qw reconcile` and `qw reconcile --json` both run and produce output.
- [ ] `qw query` presets execute with deterministic output shapes.
- [ ] `qw abort` marks target strategy ABORTED and stores reason.
- [ ] Artifact naming follows parser-inferable convention with timeframe token.

## Closed Story Traceability

This runbook baseline incorporates closed stories from both complete epic directories.

| Closed Story | Runbook basis contribution |
| --- | --- |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_0_infra_scaffold_and_docker.md` | Day-0 Neo4j setup, default timeout and graph-enabled/disabled operational assumptions |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_1_graph_v1_contract_alignment.md` | Operable contract behavior for modes, exit codes, and queue/receipt semantics |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_2_pydantic_models_and_parsers.md` | Validation error interpretation and parser constraints during operations |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_3_qw_record_cli.md` | CLI command procedures and expected exit outcomes |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_4_neo4j_idempotent_store.md` | Re-run idempotency expectations for duplicate-safe operations |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_5_shell_hooks_receipts_and_reconcile.md` | Script-level online/offline hook behavior, warning/retry visibility, and reconcile usage |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_6_readme_and_runbook_basis.md` | Epic 1 runbook baseline and operational framing |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_baseline_csv_validation_regression.md` | Baseline CSV parser regression expectations in operations |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_makefile_neo4j_lifecycle_1.md` | Canonical operator lifecycle commands (`neo4j-up/down/restart/logs/status`) |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_shell_hook_timing_race.md` | Timing-race detection and response guidance |
| `qws_graph/epics/epic_1_ingestion_and_index[COMPLETE]/closed/story_strategy_artifact_output_paths.md` | Output path and filename diagnostics that unblock ingestion |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/spike_lean_neighborhood_optimization.md` | Lean-neighborhood retrieval assumptions for operator and MCP read workflows |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_0_target_state_schema_mapping.md` | Canonical read-schema mapping guardrails |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_1_read_models_and_query_projections.md` | Typed projection outputs and query view stability |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_2_qw_query_presets.md` | `qw query` presets and parameter validation procedures |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_3_mcp_read_tool_contract.md` | MCP read adapter behavior and graph-only policy |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_4_lineage_and_pivot_queries.md` | Pivot/lineage retrieval paths for run/champion analysis |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_docs_sync_epic2.md` | Epic 2 documentation synchronization |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_family_definitions_significance_filtering.md` | Family-aware significance filtering behavior |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_family_id_backfill_migration.md` | `family_id` migration/backfill expectations |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_semantic_gate_llama4.md` | Semantic analyst fallback and `curator_note` operations |
| `qws_graph/epics/epic_2_mcp_read_integration[COMPLETE]/closed/story_strategy_family_definitions.md` | Strategy-family taxonomy context for correlation trustworthiness |
