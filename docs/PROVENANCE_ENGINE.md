# PROVENANCE ENGINE — Blueprint

> **LLM INSTRUCTION BLOCK**
> ```
> CURRENT schema nodes: Strategy, Run, Config, Champion, RetiredChampion, RunStatsSummary, BlobArtifact.
> Do NOT use Hypothesis, FormerChampion, Regime, or ResearchTarget nodes in Cypher until their
> stories are marked COMPLETE in BACKLOG_ALIGNMENT.md.
> The interface is qw CLI + MCP tools only. No FastAPI. No REST API.
> Before proposing schema changes, check this document for the authoritative current state.
> ```

---

## The Alpha Lifecycle

This is the conceptual model — the "Shared Brain" the system is being built toward.
Current state maps onto a subset of this chain. Target additions are marked.

```
[CURRENT + TARGET]

(LLM/User) -[SUGGESTED]-> (Hypothesis)
                              |
                         [TESTED_AS]
                              ↓
                         (Strategy) ←─── (Strategy) -[CORRELATED_WITH]→ (Strategy)
                              |
                          [HAS_TRIAL]
                              ↓
                           (Trial)
                              |
                        [PROMOTED_TO]
                              ↓
                          (Champion) ←── (Champion) -[CORRELATED_WITH]→ (Champion)
                         /          \
               [DEGRADED_TO]    [SUPERSEDED_BY]
                    ↓                   ↓
            (FormerChampion)       (Champion v2)
                    |
               [RETIRED_TO]
                    ↓
            (RetiredChampion)

(new Hypothesis) -[BRANCHED_FROM {rationale}]-> (any node)
```

---

## Node Types

### [CURRENT] — Implemented

| Node | Code Name | Role |
|---|---|---|
| `Strategy` | `Strategy` | Unique (instrument, timeframe, direction, logic_type) combination. Anchor for all lineage. |
| `Trial` | `Run` | A single backtest result. One node per unique (strategy_id, artifact_path, mtime). |
| `Config` | `Config` | Parameter set used for a Trial. Deduplicated — two Trials with identical params share a Config. |
| `Champion` | `Champion` | Current best-known version of a Strategy. One active Champion per Strategy. |
| `RetiredChampion` | `RetiredChampion` | Displaced Champion. Never deleted — relabeled atomically. Full lineage preserved. |
| `RunStatsSummary` | `RunStatsSummary` | Aggregate stats for grid-sweep rows below the significance gate. |
| `BlobArtifact` | `BlobArtifact` | Raw unstructured artifact (tracker markdown). Preserves provenance without parsing. |

**Vocabulary note:** "Trial" is the conceptual term for what the code calls `Run`. The node label in
Neo4j is `:Run`. When reading code or writing Cypher, use `Run`. When reasoning about the lifecycle,
use "Trial."

### Strategy State Constraints

`status` is a terminal-state property on the Strategy node — not a separate node type.
An aborted strategy is a closed branch: its history is preserved, but no new Trials or
Champions may be attached to it.

| Property | Type | Current State |
|---|---|---|
| `status` | str | Enum: `ABORTED` (current) → expanding to `[ACTIVE, ABORTED, ARCHIVED]` |
| `abort_reason` | str | Mandatory when `status = ABORTED`. Captures why (e.g., "data leakage detected", "logic flaw") |
| `aborted_at` | datetime | Timestamp of `qw abort` command |

**Anti-Zombification Guardrail:** `qw record` rejects any new `:Run` or `:Champion` node
if `Strategy.status == 'ABORTED'`. To resume research on aborted logic, the researcher must
explicitly `BRANCH_FROM` it to a new Strategy via a new Hypothesis — preserving the failure
provenance in the graph.

**Query convention:** All MCP presets that traverse Strategy nodes filter with
`WHERE s.status <> 'ABORTED'` by default. Aborted strategies are only surfaced via `list_aborted`.

### [TARGET] — Not Yet Implemented

| Node | Story | Role |
|---|---|---|
| `Hypothesis` | QWS-0601 | The Spark: an unproven theory about a market inefficiency |
| `FormerChampion` | New story needed | Decay watch: alpha slipping but still monitored; sits between Champion and RetiredChampion |
| `Regime` | QWS-0502 | Market context node: `volatility_state`, `trend_state` (e.g., "Mean Reversion in High Vol") |
| `ResearchTarget` | New story needed | Config node: `sharpe_target`, `max_holding_hours`; defaulted, rarely changed, graph-queryable |

---

## Relationship Types

### [CURRENT] — Implemented

| Relationship | Source | Target | Description |
|---|---|---|---|
| `HAS_RUN` | Strategy | Run | Strategy accumulates Trials over research iterations |
| `USES_CONFIG` | Run | Config | Trial was executed with a specific parameter set |
| `PRODUCED_CHAMPION` | Strategy | Champion | Points to current active Champion (one per Strategy) |
| `WAS_CHAMPION` | Champion | RetiredChampion | Links current Champion to its predecessor. Traversable chain: `[:WAS_CHAMPION*]` |
| `PIVOTED_FROM` | Champion | Run | Links a Champion to the specific Run that triggered its promotion |
| `HAS_RUN_SUMMARY` | Strategy | RunStatsSummary | Links Strategy to rolled-up grid sweep statistics |
| `HAS_BLOB` | Strategy | BlobArtifact | Attaches raw unstructured artifact to a Strategy |

### [TARGET] — Not Yet Implemented

| Relationship | Source | Target | Properties | Story |
|---|---|---|---|---|
| `SUGGESTED` | LLM / User | Hypothesis | `source: str` (model name or "user") | QWS-0601 |
| `TESTED_AS` | Hypothesis | Strategy | — | QWS-0601 |
| `HAS_TRIAL` | Strategy | Trial | Alias for `HAS_RUN` at the conceptual level | — |
| `DEGRADED_TO` | Champion | FormerChampion | `detected_at: datetime` | New story |
| `RETIRED_TO` | FormerChampion | RetiredChampion | Replaces direct Champion→RetiredChampion in target state | New story |
| `SUPERSEDED_BY` | Champion | Champion | Replaced by better version of same idea | New story |
| `BRANCHED_FROM` | Hypothesis | Any Node | `rationale: str` — WHY this direction was taken | QWS-0601 |
| `CORRELATED_WITH` | Strategy ↔ Strategy | — | `coefficient: float`, `lookback: str`, `p_value: float`, `regime_specific: bool` | QWS-0603 |
| `CORRELATED_WITH` | Champion ↔ Champion | — | same properties (symmetric) | QWS-0603 |
| `SEMANTICALLY_RELATED` | Hypothesis ↔ Hypothesis | — | `similarity: float` (cosine) | New story |

**Name conflict note:** `PIVOTED_FROM` already exists in the current schema (Champion → Run, meaning "this
champion was promoted based on this run"). The new target "context bridge" relationship uses a different
name — `BRANCHED_FROM` — to avoid ambiguity. The Hypothesis points BACK to whatever node sparked it.

---

## [CURRENT] Key Properties

### Trial (Run) — most important for queries

| Property | Type | Description |
|---|---|---|
| `run_id` | str | Deterministic 12-char hex ID |
| `sharpe` | float | Sharpe ratio. Core quality signal. |
| `evidence_score` | float | `sharpe * sqrt(total_trades)`. Primary sort axis. |
| `total_trades` | int | Sample size denominator |
| `profit_factor` | float | Gross profit / gross loss |
| `max_drawdown` | float | Peak-to-trough equity decline (negative, e.g. -0.087) |
| `metrics_return` | float | Realized percentage return (fraction) |
| `total_r` | float | Sum of R-multiples. Position-sizing independent. |
| `tier` | str | `fail \| professional \| institutional` |
| `oos_status` | str | `oos_pending \| oos_pass \| oos_fail` |
| `artifact_path` | str | Repo-relative POSIX path to source CSV |
| `peaked_as_best` | bool | Permanent flag: was ever Strategy.best_run_id |

### [TARGET] Trial — Properties to Be Added

These properties do not exist in the current schema. Do not query them until the implementing
story is marked COMPLETE in `BACKLOG_ALIGNMENT.md`.

| Property | Type | Formula / Source | Purpose |
|---|---|---|---|
| `active_window_frequency` | float | `total_trades / (last_trade_ts − first_trade_ts)` in days | Trades-per-day over the active window only. Prevents dilution from flat regime gaps. Required for the significance gate (≥ 0.06). |
| `duty_cycle` | float | `active_days / total_backtest_days` | Fraction of backtest period in which the target regime was present. Portfolio heat signal — not a promotion gate. |
| `first_trade_ts` | datetime | Sourced from trade log | Timestamp of first closed trade. Anchor for active-window calculation. |
| `last_trade_ts` | datetime | Sourced from trade log | Timestamp of last closed trade. Anchor for active-window calculation. |

### Champion — key query properties

| Property | Type | Description |
|---|---|---|
| `champion_id` | str | 12-char hex ID |
| `metrics_sharpe` | float | Sharpe at time of promotion |
| `metrics_return` | float | Realized return at time of promotion |
| `oos_status` | str | `oos_pending \| oos_pass \| oos_fail` |
| `oos_date` | date | ISO date of last `qw record --oos` call; null until first update |
| `auto_promoted` | bool | true = auto-gate; null = manually curated (authoritative) |
| `fragilities` | list[str] | Known failure modes |

---

## MCP Tools — Query Interface

All tools are read-only. Call via `qw query --name <preset>`.
JSON output: append `--json` to any preset. Pipe to `jq` for filtering.

### [CURRENT] Active Tools

| Preset | Purpose |
|---|---|
| `recent_champions` | All active Champions, sorted by evidence |
| `strategy_lineage` | Full history for one Strategy (Trials + Champions) |
| `run_history` | All Trials for a Strategy, ranked by evidence_score |
| `downstream_champions` | Champions downstream of a specific Run. **Update (QWS-0504):** add `depth` param |
| `cross_artifact_correlation` | Strategies sharing the same family_id |
| `portfolio_alpha` | All OOS-pass Champions with aggregate metrics |
| `instrument_concentration` | Champions grouped by instrument |
| `pending_offline` | Artifacts in `.qws/pending/` not yet ingested |

### [DECOM] Tools Being Removed

| Preset | Reason |
|---|---|
| `rank_by_evidence` | Redundant — duplicate of `run_history` |
| `trace_champion` | Redundant — duplicate of `downstream_champions` |
| `fragility_report` | Replaced — fragility signals distributed across `portfolio_alpha`, `former_champions`, `regime_performance` (see below) |
| `staleness_report` | Low value — clutters the MCP interface |

### [TARGET] New Tools (by story)

| Preset | Story | Purpose |
|---|---|---|
| `list_oos_pending` | QWS-0406 | Champions missing OOS results — current priority surface |
| `list_aborted` | QWS-0406 | All Strategies where `status = ABORTED`, with `abort_reason` and `aborted_at`. LLM checks this before suggesting any new strategy. |
| `promotion_candidates` | QWS-0406 | Runs meeting `standards.py` tier thresholds not yet promoted. Dual-hurdle gate: `total_trades >= 30` AND `active_window_frequency >= 0.06 trades/day`. Output includes **Tier** (Professional / Institutional), **Active-Window Frequency**, and **Regime Diversity Score** — so the LLM can distinguish "Regime Specialist" from "Robust Performer" before recommending promotion. |
| `regime_performance` | QWS-0503 | Performance table grouped by `--regime` property. Includes **Regime Diversity Score** (count of distinct regimes meeting Sharpe threshold). Score = 1 → "Regime Specialist" (fragility flag). |
| `former_champions` | Epic 4/5 | The "Cemetery" view: strategies that failed OOS or were retired |
| `hypothesis_audit` | QWS-0601 | Traces current state back to the original `curator_note` intent |

### [TARGET] Fragility Signal Distribution

`fragility_report` is not simply removed — its risk signals are promoted into three tools
where they have more context:

| Tool | Fragility Signal |
|---|---|
| `portfolio_alpha` | Adds MaxDD and Calmar filters. Champions where OOS performance deviates significantly from IS "Golden Run" metrics are highlighted as high-risk. |
| `former_champions` | Cemetery audit: LLM checks whether a proposed strategy is a reskin of a FormerChampion that previously failed (`oos_status = "FAIL"`). Output **must include `oos_reason` / `retirement_note`** — the most valuable data point is *why* the strategy died (e.g., "MaxDD breach during CPI vol"). Without cause-of-death, the LLM cannot reason about whether the reskin avoids the original failure mode. |
| `regime_performance` | Ultimate fragility test: reveals if a strategy only works in one regime (e.g., "Bull Trend") and collapses in others (e.g., "High Volatility"). Output includes a **Regime Diversity Score** (count of distinct regimes in which the strategy met the Sharpe threshold). Score = 1 → "Regime Specialist" (specific fragility class). Score ≥ 3 → regime-robust. |

**Fragility classification rules for the LLM:**
- `portfolio_alpha` shows OOS/IS deviation beyond threshold → **IS/OOS Drift**
- `former_champions` contains a structurally similar strategy with matching failure mode → **Known Dead Edge**
- `regime_performance` Diversity Score = 1 → **Regime Specialist**
- Any combination of the above → flag before promotion recommendation

**Schema note:** `oos_reason` and `retirement_note` are new properties on `FormerChampion` /
`RetiredChampion` — not yet in the current schema. Required when FormerChampion story is implemented.

---

## [TARGET] Promotion Gate (correlation-gated)

Current gate: `sharpe >= 2.0 AND evidence_score > current_champion.evidence_score`

Target gate adds correlation guard:
```
IF (Trial.sharpe >= ResearchTarget.sharpe_target)
   AND (Trial.evidence_score > current_champion.evidence_score)
   AND (Trial.corr_to_all_champions < 0.30)
THEN PROMOTED_TO Champion
ELSE IF corr_check_failed: flag "Redundant Beta — consider BRANCHED_FROM new Hypothesis"
```

This requires `CORRELATED_WITH` edges to exist (QWS-0603).

---

## [TARGET] Recursive Validation Loop

Scheduled MCP skill (`monitor_champion`) re-runs a Trial on every active Champion with fresh data.

```
IF abs(new_trial.sharpe - champion.metrics_sharpe) > decay_threshold:
    CREATE (FormerChampion) from current Champion
    CREATE (Champion)-[DEGRADED_TO]->(FormerChampion)
    NOTIFY Will: "Strategy-X hit decay threshold. Moved to FormerChampion. Pivot or retire?"

Will's options:
    a) CREATE (new Hypothesis)-[BRANCHED_FROM {rationale}]->(FormerChampion)  → research pivot
    b) CREATE (FormerChampion)-[RETIRED_TO]->(RetiredChampion)               → archive
```

---

## [TARGET] BRANCHED_FROM — The Context Bridge

The most important target relationship. Prevents context loss at session boundaries.

```cypher
// When pivoting from a Trial that had good Sharpe but high drawdown:
CREATE (h:Hypothesis {hypothesis_id: $id, text: "tighten stop-loss to improve risk profile"})
CREATE (h)-[:BRANCHED_FROM {rationale: "cl-1h-bear-ls trial 63bcef04 showed Sharpe 2.3 but -18% DD"}]->(t:Trial {run_id: "63bcef04513b"})
```

Query patterns:
```cypher
// Why does this Hypothesis exist?
MATCH (h:Hypothesis {hypothesis_id: $id})-[:BRANCHED_FROM]->(source) RETURN source

// What research branches came from this Trial?
MATCH (h:Hypothesis)-[:BRANCHED_FROM]->(t:Trial {run_id: $run_id}) RETURN h

// Full pivot history from a FormerChampion:
MATCH (h:Hypothesis)-[:BRANCHED_FROM*]->(fc:FormerChampion) WHERE fc.strategy_id = $sid RETURN h
```

---

## Reference Files

- `qws_graph/docs/data_dictionary.yaml` — authoritative current schema (all properties)
- `qws_graph/docs/graph_v1_contract.md` — implementation contract
- `qws_graph/docs/qws_graph_runbook.md` — operational procedures
- `docs/BACKLOG_ALIGNMENT.md` — which stories implement which target nodes
