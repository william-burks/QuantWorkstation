# BACKLOG ALIGNMENT — Connector

> **LLM INSTRUCTION BLOCK**
> ```
> Before any implementation work:
>   1. Check the Epic Status table — do not implement capabilities from PLANNED stories
>   2. Check "Not Yet Implemented" — do not reference these nodes, properties, or tools in Cypher
>   3. New story candidates at the bottom are proposals only — Will decides before scoping
>
> Current sprint: Epic 5 COMPLETE — next: QWS-0601 (Hypothesis Journaling) or QWS-0802 (SUPERSEDED_BY)
> ```

---

## Epic Status

| Epic | Status | Objective |
|---|---|---|
| Epic 1 — Ingestion & Index | **COMPLETE** | Neo4j ingestion pipeline, CLI, shell hooks |
| Epic 2 — MCP Read Integration | **COMPLETE** | Query presets, MCP tools, semantic gate |
| Epic 3 — Research Pipeline Integrity | **COMPLETE** | Schema consistency, Trial bundle, UAT runbook |
| Epic 4 — Workflow Utility | **COMPLETE** | OOS tracking, promotion alerts, query interface |
| Epic 5 — Context Enrichment | **PLANNED ← current** | family_id, Regime tagging, cross-instrument aggregation |
| Epic 6 — Research Analytics | **PLANNED** | Hypothesis journaling, parameter stability, portfolio correlation |
| Epic 7 — Developer Experience | **PLANNED** | PyPI packaging, CI integrity gate |

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
| Semantic Hypothesis Deduplication | QWS-0604 (**TESTING**) | `SEMANTICALLY_RELATED` edges between Hypothesis nodes; `similar_hypotheses` preset; `embedding` property on Hypothesis; `qw backfill --embeddings`; check_redundancy gains semantic upgrade (reads SEMANTICALLY_RELATED edges) | — |

### Epic 8 — Champion Lifecycle

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| FormerChampion Lifecycle | QWS-0801 | `FormerChampion` node; `DEGRADED_TO` + `RETIRED_TO` edges; `oos_reason` / `retirement_note` properties; `qw degrade` / `qw retire` CLI; `former_champions` preset | QWS-0402 CLOSED |
| SUPERSEDED_BY Relationship | QWS-0802 | `SUPERSEDED_BY` edge created at promotion time; direct one-hop lineage from displaced Champion to successor | — |
| Recursive Validation Loop | QWS-0803 | `qw monitor` CLI; `monitor_champion` skill; auto-creates `DEGRADED_TO` on decay threshold breach; BlobArtifact notification | QWS-0801 CLOSED |

### Epic 7 — Developer Experience

| Story | ID | Capabilities Unlocked |
|---|---|---|
| PyPI Packaging | QWS-0701 | `strategy_utils` package importable from PyPI; cross-repo reuse |
| CI Graph Integrity Gate | QWS-0702 | `make test-integrity` runs 5 integrity checks on every push |

---

## Not Yet Implemented

Do not reference any of the following in Cypher queries or implementation code until
the linked story is marked COMPLETE above.

### Nodes
| Node | Story |
|---|---|
| `FormerChampion` | QWS-0801 |

### Relationships
| Relationship | Story |
|---|---|
| `DEGRADED_TO` | QWS-0801 |
| `SUPERSEDED_BY` | QWS-0802 |
| `RETIRED_TO` (FormerChampion→RetiredChampion) | QWS-0801 |
| `CORRELATED_WITH` | QWS-0603 (**IMPLEMENTED**) |
| `SEMANTICALLY_RELATED` | QWS-0604 |

### Properties
| Property | Node | Story |
|---|---|---|
| `oos_reason` | FormerChampion / RetiredChampion | QWS-0801 |
| `retirement_note` | FormerChampion / RetiredChampion | QWS-0801 |
| `embedding` | Hypothesis | QWS-0604 |
| `status = ARCHIVED` | Strategy | QWS-0406 amendment (ABORTED exists; ARCHIVED is new) |

### MCP Tools
| Tool | Story |
|---|---|
| `former_champions` | QWS-0801 |
| `monitor_champion` | QWS-0803 |
| `similar_hypotheses` | QWS-0604 |

---

## New Story Candidates

Identified during vision planning — not yet in the backlog. Will decides priority before scoping.

| Candidate | What it delivers |
|---|---|
| `qw promote` explicit CLI command | Separates the promotion decision from `qw record --bundle`. Allows staged promotion: record many trials, then selectively promote. Re-runnable correlation gate (re-check after portfolio composition changes without re-running a trial). Auditable promotion event in graph. Value only if workflow shifts to deferred/batch promotion. |

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
```

---

## Reference Documents

- `docs/MANIFESTO.md` — mission, targets, philosophy
- `docs/PROVENANCE_ENGINE.md` — authoritative schema and MCP tool reference
- `docs/RESEARCH_WORKFLOW.md` — research loop, interaction modes, pivot tracking
- `qws_graph/epics/INDEX.md` — canonical story status (source of truth for COMPLETE/PLANNED)
