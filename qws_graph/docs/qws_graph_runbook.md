# qws_graph Runbook

Operator runbook for Graph V1 as currently implemented in QuantWorkstation.

## Intended Behavior Now

- Existing research scripts remain the execution entrypoints.
- Graph ingestion is post-run and soft-fail (`qw record ... || true`).
- Online mode writes to Neo4j and receipts.
- Offline mode writes to pending queue and receipts with `pending_offline` status.
- Re-ingest is idempotent by deterministic IDs and MERGE semantics.

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
- Neo4j Browser reachable at `http://localhost:7474` (from Story 0 quickstart context).

### 2) Verify CLI availability
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --help
qw reconcile --help
```

Expected:
- `qw record` shows required `--file`, `--kind` and current options.
- `qw reconcile` shows `--since`, `--json`, `--repo-root`.

## Day-1 Operations

### Online ingestion path
Use this when Neo4j is up and reachable.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv
```

Expected:
- Exit `0` on success.
- Receipt written to `.qws/receipts/<id>.json` with `status: persisted`.

### Offline ingestion path
Use this when Neo4j is intentionally disabled or unavailable.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --offline
```

Expected:
- Exit `0` on success.
- Pending payload in `.qws/pending/<id>.json`.
- Receipt in `.qws/receipts/<id>.json` with `status: pending_offline`.

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

Expected:
- Research script runs as normal.
- Hook attempts post-run ingestion.
- Successful ingestion writes receipt files under `.qws/receipts/`.

#### Phase 2 shell run with graph disabled (offline queue)
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/run_es_phase2.sh 1a
```

Expected:
- Research script runs as normal.
- Hook uses `qw record ... --offline || true`.
- Successful offline ingest writes pending payloads under `.qws/pending/` and receipts under `.qws/receipts/`.

#### Phase 2 shell run to verify warning/retry visibility
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true QW_GRAPH_PORT=1 zsh research/run_es_phase2.sh 1a
```

Expected:
- STDERR includes `WARNING: Neo4j unavailable (timeout after 3s)`.
- STDERR includes retry guidance to start Neo4j or rerun with `--offline`.
- Script still completes because hook execution remains soft-fail.

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

If the timeframe token is omitted, `qw record` may fail to resolve strategy fields.

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
| Missing artifact in shell hook | Script warns artifact missing and continues | Confirm strategy script wrote expected path; rerun script after fixing path/name. |
| Receipt write failure | `ERROR: Failed to write receipt: ...` | Check permissions/path under `.qws/receipts`; rerun command. |
| Pending write failure in offline mode | `ERROR: Failed to write pending payload: ...` | Check `.qws/pending` permissions and disk state; rerun. |

## Troubleshooting Focus Areas

### A) Shell hook timing race (`sleep 1` safeguard)
Symptoms:
- Hook warns artifact missing right after strategy script finishes.

Checks:
1. Confirm hook still contains the `sleep 1` delay before file existence test.
2. Confirm the artifact file exists after script completion.
3. Rerun once before deeper debugging to rule out transient filesystem timing.

Related closed story:
- `qws_graph/epics/epic_1_ingestion_and_index/closed/story_shell_hook_timing_race.md`

### B) Artifact output-path mismatch
Symptoms:
- Hook expects a file path that is not created.
- `qw record` fails to infer strategy fields from file name.

Checks:
1. Verify strategy was launched with correct `--results-csv` path.
2. Verify filename includes timeframe token (example: `_1h_`).
3. Verify output directory exists and file is non-empty.

Related closed story:
- `qws_graph/epics/epic_1_ingestion_and_index/closed/story_strategy_artifact_output_paths.md`

## Verification Checklist (Current Intended Workflow)

- [ ] Neo4j lifecycle commands run via `qws_graph/Makefile`.
- [ ] `qw record` online path writes `status: persisted` receipt.
- [ ] `qw record --offline` writes pending + `status: pending_offline` receipt.
- [ ] Shell scripts complete even if ingestion fails (`|| true`).
- [ ] `qw reconcile` and `qw reconcile --json` both run and produce output.
- [ ] Artifact naming follows parser-inferable convention with timeframe token.

## Closed Story Traceability

This runbook baseline incorporates all closed Epic 1 stories.

| Closed Story | Runbook basis contribution |
| --- | --- |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_0_infra_scaffold_and_docker.md` | Day-0 Neo4j setup, default timeout and graph-enabled/disabled operational assumptions |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_1_graph_v1_contract_alignment.md` | Operable contract behavior for modes, exit codes, and queue/receipt semantics |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_2_pydantic_models_and_parsers.md` | Validation error interpretation and parser constraints during operations |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_3_qw_record_cli.md` | CLI command procedures and expected exit outcomes |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_4_neo4j_idempotent_store.md` | Re-run idempotency expectations for duplicate-safe operations |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_5_shell_hooks_receipts_and_reconcile.md` | Script-level online/offline hook behavior, warning/retry visibility, and reconcile usage |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_makefile_neo4j_lifecycle_1.md` | Canonical operator lifecycle commands (`neo4j-up/down/restart/logs/status`) |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_shell_hook_timing_race.md` | Timing-race detection and response guidance |
| `qws_graph/epics/epic_1_ingestion_and_index/closed/story_strategy_artifact_output_paths.md` | Output path and filename diagnostics that unblock ingestion |

