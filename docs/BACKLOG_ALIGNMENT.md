# BACKLOG ALIGNMENT — Connector

> **LLM INSTRUCTION BLOCK**
> ```
> Before any implementation work:
>   1. Check the Epic Status table — do not implement capabilities from PLANNED stories
>   2. Check "Not Yet Implemented" — do not reference these nodes, properties, or tools in Cypher
>   3. New story candidates at the bottom are proposals only — Will decides before scoping
>
> Current sprint: Epic 15a can start now. QWS-1304 DEFERRED — now a prerequisite for Epic 15b only (ingest path). QWS-1406 DEFERRED — not on critical path for GE direction.
>
> Confirmed sequence (2026-04-25):
>   Epic 15a: Data Health (QWS-1501/1503/1504/1505/1510) ← start now
>   Epic 17 Phase 1: GE MVP loop (grammar/decoder/fitness/engine — zero graph writes) ← parallel with 15a
>   → QWS-1304 close (prereq for Epic 15b ingest path)
>   → Epic 15b: Provenance Layer (QWS-1506a/1506b/1507/1508/1509)
>   → Epic 16: Data Collection Operations (placeholder — fully plan after QWS-1510 ships)
>   → Epic 11: Production Tracking (QWS-1101/1102) — before Epic 12/17 so MLflow live when first ML/GE champion promoted
>   → Epic 17: Grammatical Evolution (primary ML direction — Phase 1 MVP, then Phases 2–3)
>   → Epic 12: ML Research (QWS-1201 + QWS-1202 proceed in parallel with Epic 17; QWS-1203–1207 resume after GE Phase 1)
> ```

---

## Epic Status

| Epic | Status | Objective |
|---|---|---|
| Epic 1 — Ingestion & Index | **COMPLETE** | Neo4j ingestion pipeline, CLI, shell hooks |
| Epic 2 — MCP Read Integration | **COMPLETE** | Query presets, MCP tools, semantic gate |
| Epic 3 — Research Pipeline Integrity | **COMPLETE** | Schema consistency, Trial bundle, UAT runbook |
| Epic 4 — Workflow Utility | **COMPLETE** | OOS tracking, promotion alerts, query interface |
| Epic 5 — Context Enrichment | **COMPLETE** | family_id, Regime tagging, cross-instrument aggregation |
| Epic 6 — Research Analytics | **COMPLETE** | Hypothesis journaling, parameter stability, portfolio correlation, semantic dedup |
| Epic 7 — Workflow Readiness | **COMPLETE** | FormerChampion cemetery, OpenAI curation, correlation gate re-check |
| Epic 8 — Champion Lifecycle Hardening | **COMPLETE** | SUPERSEDED_BY direct lineage edge, recursive decay detection (monitor_champion) |
| Epic 9 — Strategy Development | **COMPLETE** | Research sessions, workflow observation, system gap audit — no code deliverables |
| Epic 9HF — Bugs & Hotfixes | **COMPLETE** | Fix silent data integrity bugs from Epic 9 sessions (phantom champion ID, TESTED_AS edge, branched-from node creation) |
| Epic 9.5 — Workflow Hardening | **COMPLETE** | Hypothesis lookup/findings, ad-hoc Cypher, trial metadata, CL data extension |
| Epic 10 — Macro Data | **COMPLETE** | Macro + alternative data ingestion to ArcticDB — 13 stories CLOSED, 3 moved to Epic 10b (NG/ZC/ZS now in scope) |
| Epic 10b — Commodity Regime Data | **COMPLETE** | Weather + crop alt data for NG/ZC/ZS regime conditioning — extends Epic 10 infra |
| Epic 16 — Data Collection Operations | **PLACEHOLDER** | Proactive staleness prevention: per-symbol freshness SLAs, scheduled collection orchestration, gap-detect → auto-backfill, failure alerting, unified `qw data status`. Fully plan after QWS-1510 ships. Hard dep: QWS-1510 (Data Steward Agent). |
| Epic 11 — Production Tracking | **PLANNED** | MLflow Champion registration + OOS sync; split production results from research results |
| Epic 12 — ML Research Layer | **PLANNED** | HMM regime classifier, feature engineering, LightGBM signal model, results interpreter, hypothesis miner. QWS-1201 (purge gap) + QWS-1202 (HMM) proceed. QWS-1203–1207 (LightGBM pipeline) **deprioritized** — Epic 17 GE is primary ML direction; LightGBM parallel track resumes after GE Phase 1 proves out. |
| Epic 15 — Data Infrastructure Quality & Provenance | **PLANNED** | Phase A (6 stories): bar health, Alpaca schema contract, CONTFUT revision detection, delivery monitor, roll anomaly alert, data-steward agent. Phase B (5 stories): DataSnapshot node+hash, CONSUMED_DATA edge+preset, strategy input contracts, env fingerprint, bitemporal as_of. **Insert before Epic 12 and Epic 17.** Full spec: `docs/EPIC_15_DATA_INFRASTRUCTURE.md` |
| Epic 17 — Grammatical Evolution | **PLANNED** | GE engine: BNF grammar → genome evolution → multi-instrument robustness scoring → survivor ingest to Hypothesis/Run nodes. Replaces one-at-a-time hypothesis loop with population search. Full spec: `docs/EPIC_17_GRAMMATICAL_EVOLUTION.md` |
| Epic 13 — Agent Design | **IN PROGRESS** | Research Navigator, Trial Engineer, Research Ideas Layer, Session Command Rewrite (QWS-1301/1302/1303 CLOSED; QWS-1304 BLOCKED) |
| Epic 14 — Research Pipeline Hardening | **READY** | Annual P&L breakdown, regime diversity gate, ATR regime labels, Cypher bugfix, champion degradation advisory, literature seed |
| Backlog | **UNSCHEDULED** | QWS-0701, 0702 |

---

## Story → Capability Map

### Epic 4 — Workflow Utility

| Story | ID                     | Capabilities Unlocked | Blocked On |
|---|------------------------|---|---|
| OOS Outcome Tracking | QWS-0402 (**CLOSED**)  | `oos_status` and `oos_date` on Champion node; `qw record --oos` CLI path; `list_oos_pending` (delivered by QWS-0406) | — |
| Promotion Alerts | QWS-0405 (**CLOSED**) | Notification when a Trial crosses the dual-hurdle promotion threshold | — |
| Workflow Query Presets | QWS-0406 (**CLOSED**)  | **New:** `list_oos_pending`, `promotion_candidates` (Tier + Active-Window Frequency; Regime Diversity Score deferred to QWS-0502), `list_aborted` / **Deprecated:** `rank_by_evidence`, `trace_champion` / **Retained:** `fragility_report`, `staleness_report` (deferred) / **Amended:** all Strategy traversals add `WHERE s.status <> 'ABORTED'` | — |
| Significance Gate Properties | QWS-0407 (**CLOSED**)  | `active_window_frequency`, `duty_cycle`, `first_trade_ts`, `last_trade_ts` on Run node; dual-hurdle gate | — |
| ResearchTarget Config Node | QWS-0408 (**CLOSED**)  | `ResearchTarget` singleton node; `qw seed --targets`; `research_targets` query preset | — |

### Epic 5 — Context Enrichment

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| OOS Sharpe Amendment | QWS-0402C (**CLOSED**) | `metrics_oos_sharpe` on Champion node; `--sharpe` flag on `qw record --oos` | — |
| family_id Population | QWS-0501 (**CLOSED**) | Populates `Strategy.family_id`; enables `cross_artifact_correlation` to return meaningful results | — |
| Regime Tagging | QWS-0502 (**CLOSED**) | `Regime` node; `IN_REGIME` edge (Run→Regime); `--regime` flag; `runs_by_regime` preset; partial `regime_performance` (single-strategy Diversity Score; "Regime Specialist" fragility class) | — |
| Cross-Instrument Aggregator | QWS-0503 (**CLOSED**) | Full `regime_performance` output — portfolio-wide performance table across instruments grouped by regime. Extends QWS-0502 partial preset. | ~~QWS-0501~~, ~~QWS-0402C~~ — both CLOSED |
| Recursive Lineage Traversal | QWS-0504 (**CLOSED**) | `downstream_champions` gains `depth` param for multi-hop traversal; `include_retired` flag; `get_strategy_lineage_v1` also gains `depth` | — |

### Epic 6 — Research Analytics

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Hypothesis Journaling | QWS-0601 (**CLOSED**) | `Hypothesis` node; `SUGGESTED`, `TESTED_AS`, `BRANCHED_FROM` edges; `log_hypothesis`, `check_redundancy`, `hypothesis_audit` MCP tools; full provenance chain from idea to Champion | — |
| Parameter Stability | QWS-0602 (**CLOSED**) | Stability analysis across Config parameter variations | — |
| Portfolio Correlation | QWS-0603 (**CLOSED**) | `CORRELATED_WITH` edges on Champions; `portfolio_alpha` gains MaxDD/Calmar filters + OOS/IS drift flag; correlation gate on promotion path | — |
| Semantic Hypothesis Deduplication | QWS-0604 (**CLOSED**) | `SEMANTICALLY_RELATED` edges between Hypothesis nodes; `similar_hypotheses` preset; `embedding` property on Hypothesis; `qw backfill --embeddings`; check_redundancy gains semantic upgrade (reads SEMANTICALLY_RELATED edges) | — |

### Epic 7 — Workflow Readiness

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| FormerChampion Lifecycle | QWS-0801 (**CLOSED**) | `FormerChampion` node; `DEGRADED_TO` + `RETIRED_TO` edges; `oos_reason` / `retirement_note` properties; `qw degrade` / `qw retire` CLI; `former_champions` preset | QWS-0402 CLOSED |
| OpenAI Curation Switch | QWS-0703 (**CLOSED**) | AI curation on by default; `--no-analyze` flag to disable; OpenAI replaces Llama; no local server required | — |
| Correlation Gate Re-check | QWS-0804 (**CLOSED**) | `qw gate --recheck` CLI; re-evaluates corr < 0.30 gate for all promotion candidates against current champion portfolio without re-running trials | QWS-0801 CLOSED |

### Epic 8 — Champion Lifecycle Hardening

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| SUPERSEDED_BY Relationship | QWS-0802 (**CLOSED**) | `SUPERSEDED_BY` edge created at promotion time; direct one-hop lineage from displaced Champion to successor | — |
| Recursive Validation Loop | QWS-0803 (**CLOSED**) | `qw monitor` CLI; `monitor_champion` skill; auto-creates `DEGRADED_TO` on decay threshold breach; BlobArtifact notification | ~~QWS-0801 CLOSED~~ (satisfied) |
| Champion Promotion Rationale | QWS-0805 (**CLOSED**) | `promotion_rationale` property on Champion node; `--rationale` flag on `qw record`; included in `recent_champions` preset output | — |

### Epic 9 — Strategy Development

| Story | ID | Deliverable | Blocked On |
|---|---|---|---|
| First Research Session | QWS-0901 (**CLOSED**) | Observation log from 3 full-stack trials (session notes live in private sibling repo — contain real champion IDs and performance) | — |
| Strategy Screening Pass | QWS-0902 (**CLOSED**) | Sweep results + redundancy check assessment (session notes live in private sibling repo) | ~~QWS-0901~~ |
| System Gap Audit | QWS-0903 (**CLOSED**) | Tooling gaps, missing data, workflow friction, AI failures, backlog candidates (lives in private sibling repo — names real hypothesis IDs) | ~~QWS-0901~~, ~~QWS-0902~~ |

### Epic 9HF — Bugs & Hotfixes

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Bundle Hypothesis Autolink + branched-from fix | QWS-HF-001 (**CLOSED**) | `hypothesis_id` in bundle.json → auto TESTED_AS edge; single-call `--hypothesis + --branched-from` creates node + edge atomically | — |
| Phantom Champion ID Fix | QWS-0904 (**CLOSED**) | Auto-promotion prints verified persisted ID (not pre-write hash); researcher can trust CLI output | — |

### Epic 9.5 — Workflow Hardening

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Hypothesis Lookup + Findings | QWS-0905 (**CLOSED**) | `findings` property on Hypothesis; `hypotheses_by_status` + `hypothesis_search` presets; `--findings` flag on `qw record --hypothesis` | — |
| Ad-hoc Cypher + `qw patch` | QWS-0906 (**CLOSED**) | `qw query --cypher` read-only passthrough; `qw patch --run` for surgical property corrections | — |
| Trial Metadata JSON Blob | QWS-0907 (**CLOSED**) | `trial_metadata` map property on Run node; regime columns survive bundle ingest | — |
| CL Historical Data Extension | QWS-0908 (**CLOSED**) | CL 1H data extended to ≥ 2020 via IBKR audit or FirstRate CSV ingest | — |

### Epic 13 — Agent Design

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Research Ideas Layer | QWS-1301 (**CLOSED**) | `queued` flag on Hypothesis; `queued_hypotheses` preset; lightweight mid-session idea intake; `BRANCHED_FROM` to Run | ~~QWS-HF-001~~, ~~QWS-0905~~ |
| Research Navigator Agent | QWS-1302 (**CLOSED**) | `research-navigator` agent; ranked next-direction synthesis; Phase 3 mid-session pivot; proactive redundancy check | ~~QWS-1301~~ |
| Trial Engineer Agent | QWS-1303 (**CLOSED**) | `trial-engineer` agent; generates trial script + bundle.json from hypothesis context; stops before run | ~~QWS-1302~~ |
| Research Session Command Rewrite | QWS-1304 (**BLOCKED**) | `/research-session` orchestrates navigator + trial-engineer; handoff contract defined | ~~QWS-1302~~, ~~QWS-1303~~ |

### Epic 14 — Research Pipeline Hardening

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Year-by-Year P&L | QWS-1401 (**CLOSED**) | `annual_pnl_breakdown()` in metrics.py; annual table in evaluator.report(); regime concentration warning | — |
| Regime Diversity Gate | QWS-1402 (**CLOSED**) | `diversity_score()` in metrics.py; diversity block in evaluator.report(); `diversity_score`, `diversity_years_positive`, `diversity_distinct_years` in `trial_metadata` on Run node | ~~QWS-1401~~ |
| ATR Regime Pre-Labels | QWS-1403 (**CLOSED**) | `research/regimes/atr_trend_classifier.py`; `regime_atr_{symbol}_{tf}` series in ArcticDB signals lib for CL_1H, MES_1H, BTC/USD_1H | — |
| Fix Redundancy Gate Cypher | QWS-1404 (**CLOSED**) | `check_redundancy` returns correct results (no cartesian product duplicates) | — |
| Champion Degradation Advisory | QWS-1405 (**CLOSED**) | `qw monitor --audit-lineage`; advisory output for lineage-rejected Champions; `qw degrade --reason`; `degrade_reason` on FormerChampion | — |
| Seed Literature Pipeline | QWS-1406 (**DEFERRED**, private) | ≥5 papers in `~/ClaudeProjects/QuantWorkstation-private/qws_researcher/data/extracts/`; `search_library()` returns hits for mean reversion and regime switching queries. Story + pipeline live in private sibling repo. Deferred 2026-04-25 — not on critical path for GE direction. | — |

### Epic 15 — Data Infrastructure Quality & Provenance

> Full spec at `docs/EPIC_15_DATA_INFRASTRUCTURE.md`. Phase A before Phase B. Both before Epic 12.

**Phase A: Data Health (QWS-1501–1505, QWS-1510)** — sprint order: 1501 ∥ 1502 ∥ 1504, then 1503 → 1505, then 1510

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| ArcticDB Bar Health Report | QWS-1501 (**PLANNED**) | `scripts/bar_health.py`; `audit_symbol()` in `data/validation.py`; `Store.get_symbol_info()` in `data/store.py`; per-symbol audit table; non-zero exit gate | — |
| Vendor Schema Contract — Alpaca | QWS-1502 (**DEFERRED — post-MVP**) | Crypto-only. Fully specced in `EPIC_15_DATA_INFRASTRUCTURE.md`. Reactivate when crypto re-enters scope. | — |
| CONTFUT Revision Detection | QWS-1503 (**PLANNED**) | Revision comparison on CONTFUT collect (threads `adjusted: bool` through `_bars_to_df()` call chain); warns on >0.5% close delta; fixes `adjusted=True` metadata on CONTFUT + final stitched output | After QWS-1502 (sequential, shared `ibkr_futures.py`) |
| Collector Delivery Monitor | QWS-1504 (**PLANNED**) | `scripts/check_feeds.py`; uses `Store.get_symbol_info()`; STALE/OK per symbol; non-zero exit on STALE; <15s runtime | — |
| IBKR Roll Anomaly Alert | QWS-1505 (**PLANNED**) | `RollAnomalyError` in `data/validation.py`; guard on individual roll ratio in `_ratio_stitch()`; [0.80, 1.20] configurable bounds; fallback path logs WARNING only | After QWS-1503 (sequential, shared `ibkr_futures.py`) |
| Data Steward Agent | QWS-1510 (**PLANNED**) | `.claude/agents/data-steward.md`; `.claude/scripts/agent-data-guard.sh`; session-start gate (bar_health + check_feeds → halt on P1/STALE); Prefect incident triage; research-navigator Phase 1 updated; RESEARCH_WORKFLOW.md startup section complete | QWS-1501, QWS-1504 |

**Phase B: Provenance Layer (QWS-1506a–1509)** — sprint order: 1506a first, then 1506b ∥ (1507 → 1508) ∥ 1509

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| DataSnapshot Node + Hash | QWS-1506a (**PLANNED**) | `Store.snapshot_id()`; `DataSnapshot` dataclass in `research/graph/models.py`; `make_bundle(data_snapshots=...)` in `trial_base.py`; `docs/graph/data_dictionary.yaml` updated; Neo4j constraint documented | — |
| CONSUMED_DATA Edge + Preset | QWS-1506b (**PLANNED**) | `DATA_SNAPSHOT_INGEST_QUERY` + `CONSUMED_DATA_EDGE_QUERY` in `cypher.py`; `GraphStore.write_data_snapshot()`; `_cmd_bundle()` writes edges; `run_data_lineage` preset; `PROVENANCE_ENGINE.md` DataSnapshot + CONSUMED_DATA sections | QWS-1506a |
| Strategy Input Contract | QWS-1507 (**PLANNED**) | `InputContract` NamedTuple; `BaseStrategy.input_contracts ClassVar`; `qw validate --strategy` CLI subparser; `REQUIRES` edge Strategy→InputSpec; trial-engineer Step 0b; `PROVENANCE_ENGINE.md` updated | — (sequential before QWS-1508) |
| Environment Fingerprint on Run | QWS-1508 (**PLANNED**) | `python_version`, `pkg_lock_hash`, `random_seed` on Run node (all Optional); auto-populated at ingest; `env_drift` preset | After QWS-1507 (shared `research/graph/models.py` + `cypher.py`) |
| Bitemporal as_of on Runs | QWS-1509 (**PLANNED**) | `data_as_of` datetime on Run (Optional); derived from CONSUMED_DATA → DataSnapshot timestamps; `stale_data_runs` preset | QWS-1506a |

### Epic 16 — Data Collection Operations *(placeholder — fully plan after QWS-1510 ships)*

> Hard prerequisite: QWS-1510 (Data Steward Agent). Story IDs and ACs not assigned yet.
> The steward agent will expose which freshness signals are cheap to check and which sources fail in practice — design SLAs from that evidence, not speculation.

| Story bucket | What it covers | Notes |
|---|---|---|
| Freshness SLAs | Per-symbol/timeframe config: max staleness before STALE flag | Driven by what QWS-1510 sessions reveal about real failure modes |
| Scheduled collection | Prefect (or cron) orchestration for Alpaca + IBKR collectors | Builds on existing `data/flows/` Prefect infra from QWS-1100b/c |
| Gap-detect → backfill | QWS-1501 gap signal triggers automatic collector run for missing window | Closes the reactive→proactive gap left by QWS-1501 |
| Failure alerting | Collection run fails → lightweight notification (log + email threshold) | Scope TBD after seeing real failure frequency |
| Unified status view | `qw data status` — freshness across all symbols in one command | Wraps `check_feeds.py` (QWS-1504) + SLA config |

### Epic 12 — ML Research Layer

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Walk-forward Purge Gap | QWS-1201 (**READY**) | `purge_bars` parameter on `walk_forward.py`; prevents rolling feature leakage between folds | — |
| HMM Regime Classifier | QWS-1202 (**READY**) | `research/models/hmm_regime.py`; per-bar regime labels via existing `qw record --regime` path; `Strategy.logic_type = "ml_regime"`, `model_class = "hmm"` | QWS-1201 |
| Feature Engineering Layer | QWS-1203 (**PLANNED**) | `research/features/` YAML specs; `feature_builder.py`; lookahead guard; starter feature library | QWS-1201 |
| ML Walk-forward Harness | QWS-1204 (**PLANNED**) | `ml_walk_forward.py`; Optuna inner loop; overfitting flags; output CSV compatible with `qw record --bundle` | QWS-1203 |
| LightGBM Signal Model | QWS-1205 (**PLANNED**) | `strategies/ml_signal_strategy.py`; `generate_signals()` via trained artifact; same vectorbt path as rule-based | QWS-1204 |
| Results Interpreter Agent | QWS-1206 (**PLANNED**) | `/interpret-ml-results` skill; `verdict.md` per experiment; PROMOTION_CANDIDATE / OVERFIT / FAIL verdicts | QWS-1204 |
| Hypothesis Miner Agent | QWS-1207 (**PLANNED**) | `/mine-ml-hypotheses` skill; proposal files in `research/ideas/` with graph-node citations | QWS-1206 |

### Epic 10b — Commodity Regime Data

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| NOAA Degree Days | QWS-1005 (**CLOSED**) | HDD/CDD data in ArcticDB `macro` lib; NG regime conditioning | — |
| USDA Crop Progress | QWS-1006 (**CLOSED**) | Weekly crop progress data; ZC/ZS regime conditioning | — |
| NDVI Crop Health | QWS-1011 (**CLOSED**) | NASA AppEEARS NDVI anomaly; ZC/ZS crop health regime signal | — |
| Macro Collection Prefect Flow | QWS-1013 (**CLOSED**) | Scheduled macro data collection; `data/flows/macro.py` deployment | — |

### Epic 10 — Macro Data

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Store Series Methods | QWS-1000 (**CLOSED**) | `write_series`/`read_series` for non-OHLCV data in ArcticDB | — |
| COT Collector | QWS-1001 (**CLOSED**) | CFTC COT positioning data in ArcticDB | ~~QWS-1000~~ |
| FRED Macro Collector | QWS-1002 (**CLOSED**) | FRED macro indicators in ArcticDB | ~~QWS-1000~~ |
| EIA Crude Collector | QWS-1003 (**CLOSED**) | EIA crude inventory + production data in ArcticDB | ~~QWS-1000~~ |
| Baker Hughes Rig Count | QWS-1004 (**CLOSED**) | Weekly rig count data in ArcticDB | ~~QWS-1000~~ |
| NOAA Degree Days | QWS-1005 (**MOVED → Epic 10b**) | Moved to Epic 10b — NG now in scope | ~~QWS-1000~~ |
| USDA Crop Progress | QWS-1006 (**MOVED → Epic 10b**) | Moved to Epic 10b — ZC/ZS now in scope | ~~QWS-1000~~ |
| Google Trends | QWS-1007 (**CLOSED**) | Google Trends signals in ArcticDB | ~~QWS-1000~~ |
| BDTI Tanker Index | QWS-1008 (**CLOSED**) | Baltic Dirty Tanker Index data in ArcticDB | ~~QWS-1000~~ |
| Economic Calendar Collector | QWS-1009 (**CLOSED**) | Economic event calendar data in ArcticDB | ~~QWS-1000~~ |
| Data Quality Validation | QWS-1010 (**CLOSED**) | Validation gate — alerts on missing bars, stale feeds, schema drift | — |
| NDVI Crop Health Collector | QWS-1011 (**MOVED → Epic 10b**) | Moved to Epic 10b — ZC/ZS now in scope | ~~QWS-1000~~ |
| Strategy Class Taxonomy | QWS-1012 (**CLOSED**) ⚠️ | `strategy_class` free-form string on Strategy; `portfolio_by_class` preset; `qw backfill --strategy-class`; `bundle.json` reads `strategy_class` | — |
| Scheduler Isolation | QWS-1100a (**CLOSED**) | `execution/risk_scheduler.py` with risk jobs only; `prefect` in pyproject.toml | — |
| Prefect Flows | QWS-1100b (**CLOSED**) | Scheduled collection via Prefect flows; 5 `data/flows/` files; 4 deployments registered | ~~QWS-1100a~~ |
| Prefect Daemon | QWS-1100c (**CLOSED**) | launchd daemon; `prefect.db` + `mlruns/` in `.gitignore`; all 4 deployments live | ~~QWS-1100b~~ |

### Epic 11 — Production Tracking

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| MLflow Champion Registration | QWS-1101 (**READY**) | `qw mlflow register`; IS params/metrics/artifacts logged to local MLflow at promotion time; `mlflow_run_id` written to Champion node | ~~QWS-0801 CLOSED~~ |
| MLflow OOS Sync | QWS-1102 (**READY**) | `qw mlflow sync-oos`; live OOS metrics synced back to existing MLflow run | QWS-1101 |

### Epic 17 — Grammatical Evolution

> Full spec at `docs/EPIC_17_GRAMMATICAL_EVOLUTION.md`. Phase 1 before Phase 2/3. All phases blocked on prerequisites below.
>
> Prerequisites: QWS-1304 CLOSED, Epic 15A CLOSED (QWS-1501/1503/1504/1505/1510), QWS-1506a + QWS-1506b CLOSED, QWS-1201 CLOSED.
>
> Phase execution: QWS-1701 → QWS-1702 → QWS-1703 → QWS-1704 (Phase 1, sequential) → manual gate → QWS-1706 ∥ QWS-1705 → QWS-1707 → QWS-1708 (Phase 2/3).

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| BNF Grammar V0 + Phenotype Compiler | QWS-1701 (**PLANNED**) | `research/ge/grammar.py`; BNF Grammar class; `expand(rule)` method; phenotype compiler from AST to callable `generate_signals(df)` | Epic 17 prerequisites |
| Genome → Phenotype Mapping | QWS-1702 (**PLANNED**) | `research/ge/decoder.py`; codon-modulo BNF decoder; recursion depth guard (max=10, penalty fitness=-999) | QWS-1701 |
| Single-Instrument Fitness Evaluator | QWS-1703 (**PLANNED**) | `research/ge/fitness.py`; `evaluate(phenotype_fn, symbol, tf, df)` → `FitnessResult`; wraps `vectorbt_adapter.run()`; returns Sharpe, MaxDD, trade_count | QWS-1702 |
| GE Loop V0 — In-Memory | QWS-1704 (**PLANNED**) | `research/ge/population.py` (tournament selection, one-point crossover, codon mutation, elitism); `research/ge/engine.py` (`run_evolution(config)`); `research/ge/ge_trial.py` entry point; zero graph writes; Phase 1 manual review gate | QWS-1703 |
| Multi-Instrument Robustness Scorer | QWS-1705 (**PLANNED**) | `research/ge/validator.py`; 4-instrument panel eval (MES, MNQ, CL, BTC/USD 1H); `robustness_score = percentile_25([...])` gate; only panel-passing survivors reach ingest | QWS-1704, Phase 1 manual gate |
| Population Schema | QWS-1706 (**PLANNED**) | `Population` node; `MEMBER_OF` edge (Hypothesis→Population); new Hypothesis properties: `origin`, `phenotype`, `phenotype_hash`, `genome`, `fitness_summary`; `data/graph/models.py` + `cypher.py` updated; `docs/graph/data_dictionary.yaml` updated | QWS-1704, Phase 1 manual gate |
| Survivor Ingest | QWS-1707 (**PLANNED**) | `research/ge/exporter.py`; `research/ge/hypothesis_factory.py`; `qw ge ingest --run <id> --top N`; dedup on `phenotype_hash`; Population node write; Hypothesis + MEMBER_OF writes; triggers `qw record` for Run node creation | QWS-1706 |
| MCP Filter Updates | QWS-1708 (**PLANNED**) | `list_aborted` gains `origin` field; `check_redundancy` adds `phenotype_hash` check; new `ge_population_summary` preset; `PROVENANCE_ENGINE.md` updated | QWS-1707 |

### Backlog

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| PyPI Packaging | QWS-0701 | `strategy_utils` package importable from PyPI; cross-repo reuse | — |
| CI Graph Integrity Gate | QWS-0702 | `make test-integrity` runs 5 integrity checks on every push | — |
| Research Ideas Layer | QWS-1301 (**CLOSED**) | Structured idea intake layer — see Epic 13 | Epic 13 |
| Research Navigator Agent | QWS-1302 (**CLOSED**) | Agent-guided research session navigation — see Epic 13 | Epic 13 |
| Trial Engineer Agent | QWS-1303 (**CLOSED**) | Agent that drafts and runs trial scripts — see Epic 13 | Epic 13 |
| Research Session Command Rewrite | QWS-1304 (**BLOCKED**) | Rewrite `/research-session` command — see Epic 13 | ~~Epic 13~~ |

---

## Not Yet Implemented

Do not reference any of the following in Cypher queries or implementation code until
the linked story is marked COMPLETE above.

### Nodes
_(None pending — FormerChampion implemented in QWS-0801)_

### Relationships
| Relationship | Story |
|---|---|
| `SUPERSEDED_BY` | QWS-0802 (**IMPLEMENTED**) |
| `CORRELATED_WITH` | QWS-0603 (**IMPLEMENTED**) |
| `SEMANTICALLY_RELATED` | QWS-0604 (**IMPLEMENTED**) |

### Properties
| Property | Node | Story |
|---|---|---|
| `degrade_reason` | FormerChampion | QWS-1405 |
| `embedding` | Hypothesis | QWS-0604 (**IMPLEMENTED**) |
| `promotion_rationale` | Champion | QWS-0805 (**IMPLEMENTED**) |
| `status = ARCHIVED` | Strategy | QWS-0406 amendment (ABORTED exists; ARCHIVED is new) |
| `logic_type = "ml_model"` or `"ml_regime"` | Strategy | QWS-1202 |
| `model_class` | Strategy | QWS-1202 |
| `feature_spec_path` | Strategy | QWS-1203 |

### MCP Tools
| Tool | Story |
|---|---|
| `monitor_champion` | QWS-0803 (**IMPLEMENTED**) |
| `similar_hypotheses` | QWS-0604 (**IMPLEMENTED**) |

---

## New Story Candidates

Identified during vision planning — not yet in the backlog. Will decides priority before scoping.

| Candidate | What it delivers | Instruments | Why speculative | Precondition |
|---|---|---|---|---|
| AIS Tanker Flow Tracker | Count of VLCCs loading at key crude export terminals (Ras Tanura, Basra, Fujairah). "Tanker demand index" as leading CL indicator 2–6 weeks before inventory impact. Regime signal — feeds regime classifier (QWS-1003). Not a 4H entry signal. | CL | MarineTraffic paid API (~$200/mo) or AISHub (free, limited ocean coverage). Cost not justified until CL strategies show live edge. Transit lag (2–6 weeks) limits usefulness for ≤4H holds. | CL strategy promoted to Champion with live OOS track record |

---

## Dependency Graph (target capabilities)

```
QWS-0402 (OOS tracking)
    └── QWS-0503 (cross-instrument aggregator)
    └── QWS-0603 (portfolio correlation + CORRELATED_WITH)

QWS-0501 (family_id)
    └── QWS-0503 (cross-instrument aggregator)

QWS-0601 (Hypothesis journaling)
    └── full provenance chain: Hypothesis → Strategy → Trial → Champion

QWS-0402 (OOS tracking)
    └── QWS-0801 (FormerChampion lifecycle)
            └── QWS-0803 (Recursive Validation Loop)

QWS-0601 (Hypothesis journaling)
    └── QWS-0604 (Semantic Hypothesis deduplication)

QWS-1201 (purge gap)
    ├── QWS-1202 (HMM regime classifier)
    └── QWS-1203 (feature engineering layer)
            └── QWS-1204 (ML walk-forward harness)
                    ├── QWS-1205 (LightGBM signal model)
                    └── QWS-1206 (results interpreter)
                            └── QWS-1207 (hypothesis miner)

QWS-0803 (decay monitor) — CLOSED — Epic 8 gate for Epic 12 satisfied
```

---

## Reference Documents

- `docs/MANIFESTO.md` — mission, targets, philosophy
- `docs/PROVENANCE_ENGINE.md` — authoritative schema and MCP tool reference
- `docs/RESEARCH_WORKFLOW.md` — research loop, interaction modes, pivot tracking
- `epics/INDEX.md` — canonical story status (source of truth for COMPLETE/PLANNED)
