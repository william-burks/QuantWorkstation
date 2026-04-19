# Epic 2 — Closed Stories

Sprint: MCP Read Integration  
Closed: 2026-04-05  
Stories without numbers were churned mid-sprint.

---

## Sprint Stories (Planned)

### Story 0 — Target State Schema Mapping
`story_0_target_state_schema_mapping.md`

Locked the Epic 2 read/query topology before any implementation. Confirmed that V1 graph shape
(`Strategy`, `Run`, `Config`, `Champion`, `BlobArtifact`) was sufficient for all Epic 2 read
surfaces without schema changes. Defined the canonical DTO hierarchy and the "no raw Cypher
outside query.py" guardrail that governed all downstream stories.

**Deliverable:** Approved schema mapping contract. Unblocked Stories 1–4.

---

### Story 1 — Read Models and Query Projections
`story_1_read_models_and_query_projections.md`

Built the Bridge foundation: stable, versioned DTOs for all graph read surfaces.

**Deliverables:**
- `research/graph/query_models.py` — 5 DTOs: `StrategySummaryV1`, `RunHistoryItemV1`,
  `ChampionDetailsV1`, `ConfigLinkageV1`, `StrategyLineageV1`
- `research/graph/query.py` — 7 view functions backed by Cypher; `QUERY_VIEW_REGISTRY`; `GraphQueryService`
- All outputs: deterministic, JSON-friendly flat dicts. No raw Neo4j structures exposed.

---

### Story 2 — `qw query` Presets
`story_2_qw_query_presets.md`

Implemented the operator-facing query surface on top of Story 1.

**Deliverables:**
- `research/graph/query_presets.py` — `PRESET_CATALOG`, `PresetSpec`, `validate_params`, `run_preset`
- `qw query --name <preset> --param key=value` CLI command
- 5 initial presets: `recent_champions`, `strategy_lineage`, `run_history`, `pending_offline`,
  `downstream_champions`
- `--run-history` shortcut flag; `--json` output flag

---

### Story 3 — MCP Read Tool Contract
`story_3_mcp_read_tool_contract.md`

Implemented the MCP adapter layer for agent-assisted research workflows.

**Deliverables:**
- `research/graph/mcp_adapter.py` — `MCPGraphAdapter` with `get_context_neighborhood(champion_id)`
- Adapter calls Bridge view functions; never issues raw Cypher
- MCP read contract documented: 3-key payload `{champion, strategy, pivot_config}`

---

### Story 4 — Lineage and Pivot Queries
`story_4_lineage_and_pivot_queries.md`

Acid-test for graph-ledger retrieval value. Proved real research workflows via lineage and
cross-artifact traversal.

**Deliverables:**
- `strategy_lineage` and `downstream_champions` presets (champion-to-run traversal)
- `cross_artifact_correlation` preset — correlates strategies by `logic_type + direction`
- `CrossArtifactRowV1` DTO; `StrategyLineageV1` DTO
- `RunStatsSummaryV1` DTO and `get_run_stats_summary_v1` view

---

## Spike

### Spike — Lean Neighborhood Optimization
`spike_lean_neighborhood_optimization.md`

**Risk:** Without bounding `get_context_neighborhood`, grid-sweep expansion (1,000+ Run nodes)
would cause MCP context overflow and query timeouts.

**Resolution — Option D (Curated Ingestion):** Complexity moved from query layer to ingestion
layer. Two actions:

1. **Immediate V1 safety cap:** `get_context_neighborhood(champion_id, max_runs=50)` —
   `max_runs` validated 1..200; `runs_capped: bool` flag returned; response expanded from
   3 keys to 5 (`champion`, `strategy`, `pivot_config`, `recent_runs`, `runs_capped`).
2. **Architecture direction:** Option D dependencies linked to churn stories below
   (family taxonomy, significance filtering).

---

## Churn Stories (Mid-Sprint Additions)

### Churn — Strategy Family Definitions and Significance Filtering
`story_family_definitions_significance_filtering.md`

The largest mid-sprint addition. Introduced the Curator layer between `qw record` and
`GraphStore`, and added the `family_id` property to the V1 schema.

**Deliverables:**
- `research/graph/ids.py` — `source_hash()`, `family_id()`, `run_stats_summary_id()`
- `research/graph/curator.py` — `apply_significance_gate()`: top-N Sharpe + bottom-N drawdown
  selection; `RunStatsSummary` aggregate
- `qw record --source-file` — derives `family_id` from strategy source file bytes at ingest
- `qw record --all` — bypasses significance gate
- `qw abort --strategy --reason` — marks `Strategy.status = "ABORTED"`; mandatory reason
- `Strategy.family_id`, `Strategy.status`, `Strategy.abort_reason` added to V1 schema
- `Run.curator_note` added to V1 schema
- `RunStatsSummary` node + `HAS_RUN_SUMMARY` edge + `RUN_STATS_SUMMARY_QUERY` Cypher
- `ABORT_STRATEGY_QUERY` Cypher
- `family_id` fallback OR-branch added to `GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER`
- `family_id`, `status`, `abort_reason` added to `StrategySummaryV1` and `CrossArtifactRowV1`
- `RunStatsSummaryV1` DTO; `get_run_stats_summary_v1` view

---

### Churn — Semantic Gate (Llama 4 Scout)
`story_semantic_gate_llama4.md`

Added the optional semantic annotation tier for grid-sweep candidate evaluation.

**Deliverables:**
- `research/graph/analyst.py` — `LlamaAnalyst`, `AnalystFactory`, `AnnotationResult`,
  `LlamaUnavailableError`, `truncate_curator_note()`
- `qw record --analyze` — invokes Llama 4 Scout via `QW_AI_ANALYST_ENDPOINT`; annotates
  candidates with `curator_note`; soft-fails when endpoint unavailable
- `qw query --run-history` output includes `curator_note` field
- Env vars: `QW_AI_ANALYST_ENDPOINT`, `QW_AI_ANALYST_MODEL`, `QW_AI_PROVIDER`

---

### Churn — Strategy Family Definitions (Taxonomy Spec)
`story_strategy_family_definitions.md`

Documentation story. Ratified the `family_id` naming convention and mapped all current
strategies in the repo to the taxonomy.

**Deliverables:**
- Taxonomy levels 1–4 defined (Core Logic, Signal Family, Parameter Variant, Timeframe Group)
- `family_id` convention ratified: hash-based auto-derivation via `--source-file`
- All 6 strategy files mapped: `rsi_reversion.py`, `ema_crossover.py`, `mars.py`,
  `dual_tf_trend.py`, `bear_es_sweep_1h_baseline.py`, `bear_nq_sweep_1h_baseline.py`
- `story_family_id_backfill_migration.md` drafted as follow-on

---

### Churn — family_id Backfill Migration
`story_family_id_backfill_migration.md`

Provided tooling to backfill `family_id` on pre-existing Strategy nodes. Graph was empty at
migration time — no nodes required patching.

**Deliverables:**
- `AUDIT_NULL_FAMILY_ID_QUERY` and `PATCH_FAMILY_ID_QUERY` in `cypher.py`
- `GraphStore.audit_null_family_ids() → list[dict]`
- `GraphStore.patch_family_id(strategy_id, family_id) → bool`
- `qws_graph/conftest.py` — stubs pandas before neo4j import (fixes numpy/pandas ABI
  incompatibility that blocked test collection in conda env)
- 14 unit tests; operator runbook for Path A (re-ingest) and Path B (direct patch)

---

### Churn — Baseline Ingestion Normalization
`story_baseline_ingestion_normalization.md`

Identified two issues with the first live baseline nodes (`es-1h-bear-baseline`,
`nq-1h-bear-baseline`): `family_id = null` and `logic_type = "baseline"` (non-canonical).
Documented the re-ingest procedure with `--source-file` and the root-cause investigation
for `logic_type` inference.

---

### Churn — Cross-Instrument Family Validation
`story_cross_instrument_family_validation.md`

Enabled direct family-scoped queries without requiring a `strategy_id` anchor.

**Deliverables:**
- `GET_FAMILY_CLUSTER_V1_CYPHER` — scans all strategies by `family_id` directly (Mode B)
- `get_cross_artifact_correlation_v1(session, strategy_id=None, family_id=None)` — routes
  to Mode A (anchor) or Mode B (direct family scan); `family_id` takes precedence
- `cross_artifact_correlation` preset: `strategy_id` → optional, `family_id` → optional
  (preferred); at-least-one validation in `run_preset`
- `qw query --name cross_artifact_correlation --param family_id=<hash>` now works

---

### Churn — Docs Sync: README and Runbook for Epic 2
`story_docs_sync_epic2.md`

Planned update of `README.md` and `docs/qws_graph_runbook.md` to reflect all Epic 2
capabilities. Deferred — both documents still reflect only Epic 1 at sprint close.

---

## Test Coverage at Sprint Close

| Module | Tests |
|---|---|
| `test_ids.py` | 17 |
| `test_curator.py` | 16 |
| `test_qw_abort.py` | 12 |
| `test_backfill.py` | 14 |
| `test_lineage_queries.py` | 88+ |
| `test_mcp_adapter.py` | 42 |
| `test_analyst.py` | — |
| `test_qw_query.py` | — |
| `test_graph_query_models.py` | — |
| Total passing | 227 |

Pre-existing failure (not regressions): `test_five_presets_exist` — asserts 5 presets; now 6
(`run_history` added in churn). To be fixed in docs sync story or next sprint.

---

## Open Items at Sprint Close

| Item | Story | Notes |
|---|---|---|
| `logic_type = "baseline"` non-canonical | `story_baseline_ingestion_normalization.md` | Root cause unknown; needs investigation |
| README + runbook not updated for Epic 2 | `story_docs_sync_epic2.md` | Full update deferred |
| `test_five_presets_exist` assertion stale | `test_lineage_queries.py:562` | Count is 6, not 5 |
| Baseline re-ingest with `--source-file` | `story_baseline_ingestion_normalization.md` | Blocked by pandas/numpy env fix |
