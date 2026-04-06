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
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/legacy/bear_es_sweep_1h_baseline.py
```

Expected:
- Exit `0` on success.
- Receipt written to `.qws/receipts/<id>.json` with `status: persisted`.

### Offline ingestion path
Use this when Neo4j is intentionally disabled or unavailable.

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --source-file strategies/legacy/bear_es_sweep_1h_baseline.py --offline
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
  --source-file strategies/legacy/bear_es_sweep_1h_baseline.py
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
- `research/bin/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/bin/run_es_phase2.sh`

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
QW_GRAPH_ENABLED=true zsh research/bin/run_es_nq_bear_sweep_1h_baseline.sh
```

#### Phase 2 shell run with graph disabled (offline queue)
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/bin/run_es_phase2.sh 1a
```

#### Phase 2 shell run to verify warning/retry visibility
```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true QW_GRAPH_PORT=1 zsh research/bin/run_es_phase2.sh 1a
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

---

## Appendix — Epic 3: Research Pipeline Integrity UAT Verification

End-to-end verification sequence for QWS-0304 (schema registry), QWS-0305 (centralized
ingestion), and QWS-0306 (trial bundle structure). Execute top-to-bottom from a clean
Neo4j state. Do not run against a live-data graph.

### Preconditions

Before starting, verify all of the following:

- Neo4j is running: `make neo4j-up && make neo4j-status`
- Python environment active with all deps: `pip install -e ".[dev]"`
- `qws_graph/.env` is present and correct (see `qws_graph/env.example` — credentials
  must match the running Neo4j instance; default `bolt://localhost:7687`)
- `qw --help` exits `0` (`qw` CLI is on PATH, registered via `qws_graph/pyproject.toml`)
- `jq --version` exits `0` (required for JSON pipeline examples in Phase 7)
- Run from the repo root: `cd /path/to/QuantWorkstation`
- `research/results/` is writable
- **Neo4j is empty before Phase 0** — do not run UAT against a live-data graph

---

### Phase 0 — Clean State

Nuke the graph:
```cypher
// Run in Neo4j Browser (http://localhost:7474)
MATCH (n) DETACH DELETE n;
```

Confirm empty:
```cypher
MATCH (n) RETURN count(n);
// Expected: 0
```

Clear the pending offline queue:
```zsh
rm -f .qws/pending/*.json
```
Expected: directory empty. If `.qws/pending/` is not cleared, pre-existing offline items
will appear in `qw query --name pending_offline` output and the Phase 7 empty-list check
will fail even though Phase 5 runners ingested successfully.

---

### Phase 1 — Environment Sourcing (QWS-0304)

Verify the shell runner sources `qws_graph/.env` without pre-exported graph vars.
Open a clean subshell with no graph vars set:

```zsh
env -i HOME=$HOME PATH=$PATH SHELL=$SHELL zsh
cd /path/to/QuantWorkstation
source .venv/bin/activate
./research/bin/run_liquidity_sweep_baseline.sh
```

Expected:
- Script completes without `Neo4j connectivity check failed` or similar error.
- Receipt exists in `.qws/receipts/` with `"status": "persisted"`.
- Exit `0`.

If connectivity fails, verify `qws_graph/.env` has correct `QW_GRAPH_HOST` and
`QW_GRAPH_PASSWORD` matching the running Neo4j instance.

---

### Phase 2 — Schema Audit (QWS-0304)

Verify node labels and `curator_note` property (per `graph_v1_contract.md` Run spec,
`curator_note` must be `""` — empty string — not null):

```cypher
// Labels are correct — no label-less nodes
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;
// Expected rows: ['Strategy'], ['Run'], ['Config'] (and optionally ['RunStatsSummary'])
```

```cypher
// curator_note is present on all Run nodes (empty string, not null)
MATCH (r:Run) WHERE r.curator_note IS NULL RETURN count(r) AS missing;
// Expected: 0
```

```cypher
// Spot-check a Run node
MATCH (r:Run) RETURN r.run_id, r.curator_note, r.sharpe LIMIT 3;
// Expected: curator_note = "" on each row (not null, not absent)
```

---

### Phase 3 — Centralized Ingestion Layer (QWS-0305)

Confirm no hardcoded strategy metadata remains in trial scripts:

```zsh
grep -rn 'instrument.*=.*"CL"' research/trials/
# Expected: no matches
grep -rn 'n_trades.*total_trades\|total_trades.*n_trades' research/trials/
# Expected: no matches
```

Confirm `research/graph_export.py` exists and the validation gate works:

```zsh
python - <<'EOF'
import pandas as pd
from research.graph_export import write_baseline_csv
from pathlib import Path

# Missing required field — should raise before writing
try:
    write_baseline_csv(
        pd.DataFrame([{"sharpe": 1.0}]),  # missing profit_factor, win_rate, etc.
        output_path=Path("/tmp/test_fail.csv"),
        instrument="CL", timeframe="1H", direction="bear", logic_type="liquidity-sweep",
    )
    print("FAIL — should have raised ValueError")
except ValueError as e:
    print(f"PASS — raised correctly: {e}")
EOF
```

Expected output: `PASS — raised correctly: Missing required graph export fields: {...}`

---

### Phase 4 — Trial Bundle Structure (QWS-0306)

Run the baseline and confirm bundle output:

```zsh
./research/bin/run_liquidity_sweep_baseline.sh
```

Expected directory structure:
```
research/results/futures/liquidity_sweep/runs/
  <YYYYMMDD-HHMMSS>/
    baseline_results.csv
    index.html
    bundle.json
```

Inspect the manifest:
```zsh
cat research/results/futures/liquidity_sweep/runs/*/bundle.json | python -m json.tool
# Expected: "files" key with "csv", "csv_kind", and "html" entries
```

Ingest via bundle:
```zsh
BUNDLE_DIR=$(ls -dt research/results/futures/liquidity_sweep/runs/*/ | head -1)
qw record --bundle "$BUNDLE_DIR"
```

Expected:
- Exit `0`.
- Receipt written with `"status": "persisted"`.
- Receipt includes the `run_id` generated post-parse.

Verify HTML path linked on Run node (stored as property, not BlobArtifact):
```cypher
MATCH (r:Run) WHERE r.artifact_path_html IS NOT NULL
RETURN r.run_id, r.artifact_path_html LIMIT 3;
// Expected: at least one row with a valid filesystem path
```

---

### Phase 5 — Full Pipeline Run

Run all four trial runners in sequence to populate the graph for query verification:

```zsh
./research/bin/run_liquidity_sweep_baseline.sh && \
./research/bin/run_liquidity_sweep_position_sizing.sh && \
./research/bin/run_liquidity_sweep_golden.sh && \
./research/bin/run_btc_mars_golden.sh
```

Expected: all four runners exit `0`. If any fail, stop and diagnose before proceeding
to Phase 6 — query results depend on data from all four runners.

---

### Phase 6 — Champion Promotion Verification (QWS-0304)

Verify Champion node was created after the golden run:
```cypher
MATCH (ch:Champion) RETURN ch.champion_id, ch.oos_status, ch.freeze_date;
// Expected: at least one Champion node
```

Verify end-to-end graph shape:
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
RETURN s.strategy_id, ch.champion_id, ch.oos_status;
// Expected: at least one Strategy → Champion link
```

---

### Phase 7 — Query Verification (all `qw query` presets)

Exercise every registered preset. All commands must exit `0`.

**Strategy-scoped:**
```zsh
qw query --name recent_champions
qw query --name recent_champions --param limit=5
qw query --name recent_champions --json
qw query --name strategy_lineage --param strategy_id=cl-1h-bear-liquidity-sweep
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep
qw query --run-history --param strategy_id=cl-1h-bear-liquidity-sweep   # shortcut alias — same as above
qw query --name rank_by_evidence --param strategy_id=cl-1h-bear-liquidity-sweep
```

**Champion lineage:**
```zsh
# Capture a champion_id and run_id from the data ingested in Phase 5:
CHAMPION_ID=$(qw query --name recent_champions --json | jq -r '.[0].champion_id')
qw query --name trace_champion --param champion_id=$CHAMPION_ID

RUN_ID=$(qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep \
  | head -1 | jq -r '.run_id')
qw query --name downstream_champions --param run_id=$RUN_ID
# Note: empty list is valid when no --pivot-from was used at ingest
```

**Family correlation:**
```zsh
qw query --name cross_artifact_correlation --param strategy_id=cl-1h-bear-liquidity-sweep
# Note: returns empty list when no family_id is set (requires --source-file at ingest)
# If family_id is known:
# qw query --name cross_artifact_correlation --param family_id=<12-char-hash>
```

**Portfolio-level:**
```zsh
qw query --name portfolio_alpha
qw query --name fragility_report
qw query --name staleness_report
qw query --name instrument_concentration
```

**Offline queue:**
```zsh
qw query --name pending_offline
# Expected: empty list — no artifacts stuck in queue after full pipeline run
```

**JSON output and jq pipeline:**
```zsh
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep \
  | jq 'select(.total_trades >= 10) | {run_id, sharpe, total_trades}'
```

---

### Phase 8 — Regression Check (idempotency)

Re-run the baseline a second time:
```zsh
./research/bin/run_liquidity_sweep_baseline.sh
```

```cypher
// Node counts must not double (MERGE semantics)
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;
// Expected: same counts as after Phase 2
```

---

### Phase 9 — QA Integrity Script

Run the automated structural integrity check:
```zsh
./research/bin/qa_graph_integrity.sh
```

Expected: `Passed: 5, Failed: 0`

The script checks: graph connectivity, champion presence, champion flat metrics
(`avg_sharpe` not null), champion lineage trace, and trade count significance (≥ 5).

---

### Epic 3 UAT Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `Neo4j connectivity check failed` on env-clean run | `.env` not sourced by shell runner | QWS-0304 env preamble not implemented — verify git-root-anchored env block in `research/bin/` script |
| `curator_note IS NULL` returns non-zero | `curator_note` still set to null at ingest | Check `store.py` `_persist_csv` — `curator_note` must default to `""` |
| `grep` finds `instrument.*"CL"` in trial scripts | Script not migrated to `graph_export.py` | QWS-0305 not implemented for that trial |
| `runs/<timestamp>/` directory not created | Trial script not parameterized with `--output-dir` | QWS-0306 not implemented for that trial |
| `qw record --bundle` fails with "no bundle.json" | Manifest not written by shell runner | QWS-0306 manifest generation not implemented |
| `qw query --name recent_champions` returns empty | Champion not promoted after golden run | Check QWS-0304 auto-promote gate in `store.py` |
| `artifact_path_html IS NOT NULL` returns 0 rows | HTML patch step not executed after CSV ingest | QWS-0306 two-phase write not working — check `_cmd_bundle` in `cli.py` |
| `qw query --name <preset>` returns "preset not found" | Preset not registered in PRESET_CATALOG | Check `query_presets.py` — preset may be from a newer story not yet merged |
| `downstream_champions` returns error (not empty list) | run_id doesn't exist in graph | Use a run_id from `run_history` output, not a hardcoded example value |
| `qa_graph_integrity.sh` fails Check 2 (avg_sharpe null) | Champion nodes missing flat `metrics_*` properties | Re-ingest champion markdown after confirming `CHAMPION_INGEST_QUERY` sets `ch.metrics_sharpe` |
| Node counts double on re-run | MERGE semantics broken | Do not fix here — regression in Epic 1 foundations (QWS-0301) |

---

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
| `qws_graph/epics/epic_3_research_pipeline_integrity/closed/story_4_epic3_schema_registry.md` | Schema registry + Config/Run column routing; `curator_note` default; champion auto-promote gate |
| `qws_graph/epics/epic_3_research_pipeline_integrity/closed/story_5_epic3_centralized_ingestion.md` | Centralized ingestion layer (`research/graph_export.py`); validation gate expectations |
| `qws_graph/epics/epic_3_research_pipeline_integrity/closed/story_6_trial_bundle_structure.md` | Trial bundle structure (`qw record --bundle`); per-run `runs/{ts}/`; `artifact_path_html` on `:Run` |
| `qws_graph/epics/epic_3_research_pipeline_integrity/closed/story_7_epic3_uat_runbook.md` | Epic 3 UAT appendix — 9-phase verification sequence for QWS-0304 through QWS-0306 |
