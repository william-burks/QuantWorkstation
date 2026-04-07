# BACKLOG ALIGNMENT — Connector

> **LLM INSTRUCTION BLOCK**
> ```
> Before any implementation work:
>   1. Check the Epic Status table — do not implement capabilities from PLANNED stories
>   2. Check "Not Yet Implemented" — do not reference these nodes, properties, or tools in Cypher
>   3. New story candidates at the bottom are proposals only — Will decides before scoping
>
> Current sprint: Epic 4 — Workflow Utility (QWS-0402, QWS-0405, QWS-0406)
> ```

---

## Epic Status

| Epic | Status | Objective |
|---|---|---|
| Epic 1 — Ingestion & Index | **COMPLETE** | Neo4j ingestion pipeline, CLI, shell hooks |
| Epic 2 — MCP Read Integration | **COMPLETE** | Query presets, MCP tools, semantic gate |
| Epic 3 — Research Pipeline Integrity | **COMPLETE** | Schema consistency, Trial bundle, UAT runbook |
| Epic 4 — Workflow Utility | **PLANNED ← current** | OOS tracking, promotion alerts, query interface |
| Epic 5 — Context Enrichment | **PLANNED** | family_id, Regime tagging, cross-instrument aggregation |
| Epic 6 — Research Analytics | **PLANNED** | Hypothesis journaling, parameter stability, portfolio correlation |
| Epic 7 — Developer Experience | **PLANNED** | PyPI packaging, CI integrity gate |

---

## Story → Capability Map

### Epic 4 — Workflow Utility

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| OOS Outcome Tracking | QWS-0402 | `oos_status` updates on Champions; `list_oos_pending`; partial `portfolio_alpha` update (OOS/IS drift flag only) | — |
| Promotion Alerts | QWS-0405 | Notification when a Trial crosses the dual-hurdle promotion threshold | Significance gate properties story |
| Workflow Query Presets | QWS-0406 | **New:** `list_oos_pending`, `promotion_candidates` (Tier + Active-Window Frequency; Regime Diversity Score deferred to QWS-0502), `list_aborted` / **Deprecated:** `rank_by_evidence`, `trace_champion`, `fragility_report`, `staleness_report` / **Amended:** all Strategy traversals add `WHERE s.status <> 'ABORTED'` | Significance gate properties story (for `active_window_frequency` filter in `promotion_candidates`) |

### Epic 5 — Context Enrichment

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| family_id Population | QWS-0501 | Populates `Strategy.family_id`; enables `cross_artifact_correlation` to return meaningful results | — |
| Regime Tagging | QWS-0502 | `Regime` node; `regime_performance` tool with Diversity Score; "Regime Specialist" fragility class | — |
| Cross-Instrument Aggregator | QWS-0503 | `regime_performance` full output; performance table across instruments grouped by regime | QWS-0501 + QWS-0402 |
| Recursive Lineage Traversal | QWS-0504 | `downstream_champions` gains `depth` param for multi-hop traversal | — |

### Epic 6 — Research Analytics

| Story | ID | Capabilities Unlocked | Blocked On |
|---|---|---|---|
| Hypothesis Journaling | QWS-0601 | `Hypothesis` node; `SUGGESTED`, `TESTED_AS`, `BRANCHED_FROM` edges; `log_hypothesis`, `check_redundancy`, `hypothesis_audit` MCP tools; full provenance chain from idea to Champion | — |
| Parameter Stability | QWS-0602 | Stability analysis across Config parameter variations | — |
| Portfolio Correlation | QWS-0603 | `CORRELATED_WITH` edges on Champions; `portfolio_alpha` gains MaxDD/Calmar filters + OOS/IS drift flag; correlation gate on promotion path | QWS-0402 |

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
| `Hypothesis` | QWS-0601 |
| `FormerChampion` | New story (see candidates below) |
| `Regime` | QWS-0502 |
| `ResearchTarget` | New story (see candidates below) |

### Relationships
| Relationship | Story |
|---|---|
| `SUGGESTED` | QWS-0601 |
| `TESTED_AS` | QWS-0601 |
| `BRANCHED_FROM` | QWS-0601 |
| `DEGRADED_TO` | New story |
| `SUPERSEDED_BY` | New story |
| `RETIRED_TO` (FormerChampion→RetiredChampion) | New story |
| `CORRELATED_WITH` | QWS-0603 |
| `SEMANTICALLY_RELATED` | New story |

### Properties
| Property | Node | Story |
|---|---|---|
| `active_window_frequency` | Run | New story (significance gate amendment) |
| `duty_cycle` | Run | New story (significance gate amendment) |
| `first_trade_ts` | Run | New story |
| `last_trade_ts` | Run | New story |
| `oos_reason` | FormerChampion / RetiredChampion | New story |
| `retirement_note` | FormerChampion / RetiredChampion | New story |
| `status = ARCHIVED` | Strategy | QWS-0406 amendment (ABORTED exists; ARCHIVED is new) |

### MCP Tools
| Tool | Story |
|---|---|
| `list_oos_pending` | QWS-0406 |
| `promotion_candidates` | QWS-0406 |
| `list_aborted` | QWS-0406 |
| `regime_performance` | QWS-0503 |
| `former_champions` | New story |
| `hypothesis_audit` | QWS-0601 |
| `check_redundancy` | QWS-0601 |
| `log_hypothesis` | QWS-0601 |
| `monitor_champion` | New story |

---

## New Story Candidates

Identified during vision planning — not yet in the backlog. Will decides priority before scoping.

| Candidate | What it delivers |
|---|---|
| **FormerChampion lifecycle** | `FormerChampion` node + `DEGRADED_TO` edge + `RETIRED_TO` (FormerChampion→RetiredChampion) + `oos_reason`/`retirement_note` properties + `former_champions` MCP tool. Three-stage champion decay model. |
| **Recursive Validation Loop** | `monitor_champion` scheduled skill: re-runs Trial on each Champion with fresh data; auto-creates `DEGRADED_TO` on decay threshold breach; notifies Will |
| **SUPERSEDED_BY relationship** | Links a Champion to its replacement when a better version of the same idea is promoted |
| **ResearchTarget config node** | Graph-queryable node storing `sharpe_target`, `max_holding_hours`, `min_trades`, `min_frequency`; defaulted but configurable without code changes |
| **Significance gate properties** | `active_window_frequency`, `duty_cycle`, `first_trade_ts`, `last_trade_ts` on Run node; enables dual-hurdle promotion gate |
| **Semantic Hypothesis deduplication** | `SEMANTICALLY_RELATED` edges between Hypothesis nodes via embedding similarity; guards against re-testing the same idea with different wording |

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

FormerChampion story
    └── Recursive Validation Loop story
    └── former_champions MCP tool
    └── regime_performance (fragility context)
```

---

## Reference Documents

- `docs/MANIFESTO.md` — mission, targets, philosophy
- `docs/PROVENANCE_ENGINE.md` — authoritative schema and MCP tool reference
- `docs/RESEARCH_WORKFLOW.md` — research loop, interaction modes, pivot tracking
- `qws_graph/epics/INDEX.md` — canonical story status (source of truth for COMPLETE/PLANNED)
