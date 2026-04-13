# PROVENANCE ENGINE — Blueprint

> **LLM INSTRUCTION BLOCK**
> ```
> CURRENT schema nodes: Strategy, Run, Config, Champion, RetiredChampion, FormerChampion (QWS-0801 CLOSED),
> RunStatsSummary, BlobArtifact, ResearchTarget, Regime, Hypothesis (QWS-0601 CLOSED), HypothesisSource.
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
| `FormerChampion` | `FormerChampion` | Decay watch: alpha slipping but still monitored; sits between Champion and RetiredChampion. QWS-0801. |
| `RunStatsSummary` | `RunStatsSummary` | Aggregate stats for grid-sweep rows below the significance gate. |
| `BlobArtifact` | `BlobArtifact` | Raw unstructured artifact (tracker markdown). Preserves provenance without parsing. |
| `ResearchTarget` | `ResearchTarget` | Singleton config node: promotion thresholds. Seeded via `qw seed --targets`; queried via `research_targets` preset. |
| `Hypothesis` | `Hypothesis` | The Spark: an unproven theory about a market inefficiency. QWS-0601. |
| `HypothesisSource` | `HypothesisSource` | Source of a Hypothesis (LLM model name or "user"). QWS-0601. |

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

### [NEW — QWS-0502] — Regime Context

| Node | Story | Role |
|---|---|---|
| `Regime` | QWS-0502 | Market context node keyed on researcher-defined label (e.g. "high_vol", "trend_down"). Connected to Run nodes via IN_REGIME edges. |

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
| `IN_REGIME` | Run | Regime | Links a Run to its market regime context. Created via `qw record --regime <label>`. |
| `SUGGESTED` | LLM / User | Hypothesis | `source: str` (model name or "user"). QWS-0601. |
| `TESTED_AS` | Hypothesis | Strategy | — QWS-0601. |
| `BRANCHED_FROM` | Hypothesis | Any Node | `rationale: str` — WHY this direction was taken. QWS-0601. |
| `CORRELATED_WITH` | Strategy ↔ Strategy | — | `coefficient: float`, `threshold: float`, `lookback: str`, `pair_key: str`, `computed_at: datetime`. QWS-0603. Symmetric. |
| `CORRELATED_WITH` | Champion ↔ Champion | — | same properties. QWS-0603. Symmetric. |
| `SEMANTICALLY_RELATED` | Hypothesis ↔ Hypothesis | — | `similarity: float` (cosine), `pair_key: str`, `computed_at: datetime`. QWS-0604. Symmetric. |
| `DEGRADED_TO` | Champion | FormerChampion | `detected_at: datetime`. QWS-0801. |
| `RETIRED_TO` | FormerChampion | RetiredChampion | `retired_at: datetime`. QWS-0801. |
| `SUPERSEDED_BY` | Champion | Champion | Direct one-hop lineage from displaced Champion to successor. Created atomically alongside `WAS_CHAMPION` at promotion time. Post-promotion the source carries `:RetiredChampion`. QWS-0802. |

### [TARGET] — Not Yet Implemented

| Relationship | Source | Target | Properties | Story |
|---|---|---|---|---|
| `HAS_TRIAL` | Strategy | Trial | Alias for `HAS_RUN` at the conceptual level | — |

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
| `trial_metadata` | map \| null | Free-form key-value dict from bundle.json manifest. Preserves custom columns (e.g. `atr_bucket`, `regime_label`). Null when absent or > 10KB. QWS-0907. |

### RunStatsSummary — key query properties

One node per script execution (per unique artifact path) for grid CSV ingests. Links to the
owning `Strategy` via `HAS_RUN_SUMMARY`.

| Property | Type | Description |
|---|---|---|
| `summary_id` | str | `hash12(strategy_id, artifact_path, artifact_mtime_iso)` |
| `trial_number` | int | Monotonically increasing execution counter scoped to the Strategy. Incremented once per script execution. Frozen at first write — idempotent on re-ingest. Use to track research progression: "trial 3 was the golden run; trial 7 the next refinement." |
| `total_run_count` | int | Total rows in the source CSV |
| `selected_run_count` | int | Rows that passed the significance gate and became `Run` nodes |
| `rolled_up_run_count` | int | Rows summarized (not promoted to `Run`) |
| `sharpe_mean` | float | Mean Sharpe across all rows |
| `sharpe_max` | float | Best Sharpe in the batch |
| `sharpe_min` | float | Worst Sharpe in the batch |
| `ingested_at` | datetime | Timestamp of `qw record` execution |

### [TARGET] Trial — Properties to Be Added

These properties do not exist in the current schema. Do not query them until the implementing
story is marked COMPLETE in `BACKLOG_ALIGNMENT.md`.

| Property | Type | Formula / Source | Purpose |
|---|---|---|---|
| `active_window_frequency` | float | `total_trades / (last_trade_ts − first_trade_ts)` in trades/day | Trades-per-day over the active window only. Prevents dilution from flat regime gaps. Required for the significance gate (≥ 0.06). Null only on zero-duration edge case. |
| `duty_cycle` | float \| null | `active_days / total_backtest_days` | Fraction of backtest period in which the target regime was present. Null when `backtest_start`/`backtest_end` not emitted by runner. Portfolio heat signal — not a promotion gate. |
| `first_trade_ts` | datetime | Required CSV column; sourced from trade log | Timestamp of first closed trade. Required — parse fails if absent. Anchor for active-window calculation. |
| `last_trade_ts` | datetime | Required CSV column; sourced from trade log | Timestamp of last closed trade. Required — parse fails if absent. Anchor for active-window calculation. |

### Champion — key query properties

| Property | Type | Description |
|---|---|---|
| `champion_id` | str | 12-char hex ID |
| `strategy_id` | str | FK to parent Strategy node |
| `metrics_sharpe` | float | Sharpe at time of promotion |
| `metrics_return` | float | Realized return at time of promotion |
| `metrics_total_trades` | int | Trade count at time of promotion |
| `metrics_win_rate` | float | Win rate at time of promotion |
| `metrics_profit_factor` | float | Gross profit / gross loss at time of promotion |
| `metrics_max_drawdown_r` | float | Max drawdown in R-multiples at time of promotion |
| `best_evidence_score` | float | `sharpe * sqrt(total_trades)` at time of promotion |
| `tier` | str | `professional \| institutional` |
| `freeze_date` | date | Date Champion was locked (promotion date) |
| `artifact_path` | str | Repo-relative POSIX path to source CSV |
| `metrics_summary` | str | JSON blob of all metrics at promotion time |
| `oos_status` | str | `oos_pending \| oos_pass \| oos_fail` |
| `oos_date` | date | ISO date of last `qw record --oos` call; null until first update |
| `metrics_oos_sharpe` | float \| null | OOS Sharpe from `--sharpe` flag; null until first `qw record --oos --sharpe` call |
| `auto_promoted` | bool | true = auto-gate; null = manually curated (authoritative) |
| `fragilities` | list[str] | Known failure modes |
| `promotion_rationale` | str \| null | Free-text explanation of why this strategy was promoted. Empty string when omitted. QWS-0805. |
| `created_at` | datetime | Timestamp of node creation |
| `updated_at` | datetime | Timestamp of last node update |

### Hypothesis — key properties (QWS-0601 + QWS-0604)

| Property | Type | Description |
|---|---|---|
| `hypothesis_id` | str | 12-char deterministic ID |
| `title` | str | Short description of the market inefficiency theory |
| `status` | str | `open \| confirmed \| rejected` |
| `findings` | str \| null | Free-text session notes or findings. Written via `qw record --hypothesis <id> --findings "<text>"`. Re-running overwrites. Null until first write. QWS-0905. |
| `queued` | bool | `true` if hypothesis is parked for a future session; cleared when hypothesis enters active research. **[TARGET — QWS-1301]** |
| `embedding` | list[float] | 384-dim sentence-transformer vector of `title`. Null for pre-QWS-0604 nodes; backfill via `qw backfill --embeddings`. Used to compute cosine similarity for `SEMANTICALLY_RELATED` edges. |
| `created_at` | datetime | Timestamp of node creation |
| `updated_at` | datetime | Timestamp of last node update |

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
| `former_champions` | Cemetery view: FormerChampion nodes with `strategy_id`, `instrument`, `degraded_at`, `oos_reason`, `retirement_note`, `status` (DEGRADED \| RETIRED). QWS-0801. |

### [DECOM] Tools Being Removed

| Preset | Reason |
|---|---|
| `rank_by_evidence` | Redundant — duplicate of `run_history` |
| `trace_champion` | Redundant — duplicate of `downstream_champions` |
| `fragility_report` | Replaced — fragility signals distributed across `portfolio_alpha`, `former_champions`, `regime_performance` (see below) |
| `staleness_report` | Low value — clutters the MCP interface |

### [CURRENT] Monitor Tool (QWS-0803)

| Tool | Purpose |
|---|---|
| `qw monitor` | Re-runs each active Champion's trial script with fresh data. Computes Sharpe drift. Creates DEGRADED_TO edge + FormerChampion when drift > decay_threshold. Emits notification to stdout and stores as BlobArtifact on FormerChampion. Options: `--dry-run` (report without writing), `--champion-id <id>` (scope to one). |

### [TARGET] New Tools (by story)

| Preset | Story | Purpose |
|---|---|---|
| `list_oos_pending` | QWS-0406 | Champions missing OOS results — current priority surface |
| `list_aborted` | QWS-0406 | All Strategies where `status = ABORTED`, with `abort_reason` and `aborted_at`. LLM checks this before suggesting any new strategy. |
| `promotion_candidates` | QWS-0406 | Runs meeting `standards.py` tier thresholds not yet promoted. Dual-hurdle gate: `total_trades >= 30` AND `active_window_frequency >= 0.06 trades/day`. Output includes **Tier** (Professional / Institutional), **Active-Window Frequency**, and **Regime Diversity Score** — so the LLM can distinguish "Regime Specialist" from "Robust Performer" before recommending promotion. |
| `regime_performance` | QWS-0503 | Performance table grouped by `--regime` property. Includes **Regime Diversity Score** (count of distinct regimes meeting Sharpe threshold). Score = 1 → "Regime Specialist" (fragility flag). |
| `hypothesis_audit` | QWS-0601 | Traces current state back to the original `curator_note` intent |
| `queued_hypotheses` | QWS-1301 | Returns all Hypothesis nodes with `queued=true`, ordered by `created_at` desc |

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

## [CURRENT] Recursive Validation Loop (QWS-0803)

`qw monitor` re-runs each active Champion's trial script with fresh data.

```
IF abs(new_trial.sharpe - champion.metrics_sharpe) > decay_threshold:
    store.degrade_champion(champion_id, oos_reason="Auto-detected by qw monitor on {date}: ...")
    store.attach_blob_to_former_champion(former_champion_id, artifact_type="monitor_notification", content=...)
    NOTIFY Will (stdout): "Strategy-X hit decay threshold (drift=Y). Moved to FormerChampion."

Will's options:
    a) CREATE (new Hypothesis)-[BRANCHED_FROM {rationale}]->(FormerChampion)  → research pivot
    b) qw retire <former_champion_id>                                          → archive
```

decay_threshold: read from ResearchTarget.decay_threshold; falls back to 0.75.

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
