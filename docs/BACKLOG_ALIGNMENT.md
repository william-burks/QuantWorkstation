# BACKLOG ALIGNMENT — Connector

> **LLM INSTRUCTION BLOCK**
> ```
> Before any implementation work:
>   1. Check the Epic Status table — do not implement capabilities from PLANNED stories
>   2. Check "Not Yet Implemented" — do not reference these nodes, properties, or tools in Cypher
>   3. New story candidates at the bottom are proposals only — Will decides before scoping
>
> Current sprint: Epic 13 Agent Design (QWS-1301 CLOSED; QWS-1302 CLOSED; QWS-1303 CLOSED; QWS-1304 BLOCKED — now unblocked). Epic 10 Macro Data COMPLETE. Epic 10b Commodity Regime Data COMPLETE. After Epic 13: Epic 14 Research Pipeline Hardening (6 stories READY). After Epic 14: Epic 12 ML Research.
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
| Epic 11 — Production Tracking | **PLANNED** | MLflow Champion registration + OOS sync; split production results from research results |
| Epic 12 — ML Research Layer | **PLANNED** | HMM regime classifier, feature engineering, LightGBM signal model, results interpreter, hypothesis miner |
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
| First Research Session | QWS-0901 (**CLOSED**) | `docs/research_sessions/session_0901.md` — observation log from 3 full-stack trials | — |
| Strategy Screening Pass | QWS-0902 (**CLOSED**) | `docs/research_sessions/session_0902.md` — sweep results, redundancy check assessment | ~~QWS-0901~~ |
| System Gap Audit | QWS-0903 (**CLOSED**) | `docs/epic_9_gap_audit.md` — tooling gaps, missing data, workflow friction, AI failures, backlog candidates | ~~QWS-0901~~, ~~QWS-0902~~ |

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
| Year-by-Year P&L | QWS-1401 (**READY**) | `annual_pnl_breakdown()` in metrics.py; annual table in evaluator.report(); regime concentration warning | — |
| Regime Diversity Gate | QWS-1402 (**READY**) | `diversity_score()` in metrics.py; diversity block in evaluator.report(); `diversity_score`, `diversity_years_positive`, `diversity_distinct_years` in `trial_metadata` on Run node | ~~QWS-1401~~ |
| ATR Regime Pre-Labels | QWS-1403 (**READY**) | `research/regimes/atr_trend_classifier.py`; `regime_atr_{symbol}_{tf}` series in ArcticDB signals lib for CL_1H, MES_1H, BTC/USD_1H | — |
| Fix Redundancy Gate Cypher | QWS-1404 (**CLOSED**) | `check_redundancy` returns correct results (no cartesian product duplicates) | — |
| Champion Degradation Advisory | QWS-1405 (**READY**) | `qw monitor --audit-lineage`; advisory output for lineage-rejected Champions; `qw degrade --reason`; `degrade_reason` on FormerChampion | — |
| Seed Literature Pipeline | QWS-1406 (**READY**) | ≥5 papers in `qws_researcher/data/extracts/`; `search_library()` returns hits for mean reversion and regime switching queries | — |

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
- `qws_graph/epics/INDEX.md` — canonical story status (source of truth for COMPLETE/PLANNED)
