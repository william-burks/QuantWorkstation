# Story 1 — Strategy Family Definitions & Significance Filtering

## ID
## QWS-0209C

## Status
CLOSED

## Priority
P1 — Architectural prerequisite. Grid-search ingestion is already unbounded. Every `qw record
--kind grid_csv` call today creates one `Run` + `Config` node per CSV row with no filter.
A 1,000-row sweep produces 1,000 `Run` nodes for one strategy. This must be resolved before
ingestion volume scales, not after.

## Context
This is the most significant architectural shift to date. The graph currently acts as a
**passive ledger** — it records everything that happened. This story transitions it to an
**active research journal** — it records what you learned.

The driver is the spike (`epic_2_mcp_read_integration/spike_lean_neighborhood_optimization.md`,
now CLOSED): Option A (the `max_runs=50` cap on `get_context_neighborhood`) is a runtime safety
net, not a structural fix. Option D (Curated Families) is the structural fix.

---

## Summary
Introduce a **Curator layer** that sits between `qw record` and `GraphStore.persist_artifact`.
For `grid_csv` artifacts, the Curator applies a **Significance Gate** that selects a bounded
set of instructive runs rather than ingesting every row. Unselected runs are rolled up into a
`RunStatsSummary` aggregate node. Alongside this, formalize **Strategy Families** via a
`family_id` property and add a `qw abort` command to mark dead research branches explicitly.

---

## What Exists Today (Baseline)

| Component | Current State |
|---|---|
| `research/graph/ids.py` | `strategy_id`, `run_id`, `config_id`, `champion_id` generators. No `family_id`. |
| `research/graph/models.py` | `Strategy` has `instrument`, `timeframe`, `direction`, `logic_type`. No `family_id`, no `status`. |
| `research/graph/parsers.py` | `CSVParser.parse()` ingests **all** rows unconditionally. |
| `research/graph/store.py` | `GraphStore.persist_artifact()` routes to `_persist_csv`, `_persist_champion`, `_persist_blob`. No filter hook. |
| `research/graph/cypher.py` | `CSV_INGEST_QUERY` merges one `Run` + `Config` per row. No aggregate node. |
| `research/graph/cli.py` | `qw record`, `qw reconcile`, `qw query`. No `qw abort`. |
| `research/graph/query.py` | `get_cross_artifact_correlation_v1` groups by `logic_type + direction`. `get_strategy_lineage_v1` returns `oos_status` per champion. Neither is `family_id`-aware. |

---

## Design

### 1. Family ID

A `family_id` identifies the **logic** behind a strategy, independent of instrument, timeframe,
or parameter choices. Two strategies that share the same signal source (e.g., RSI reversion on
ES and RSI reversion on NQ) share a `family_id`.

**Derivation:**
```python
# ids.py — proposed addition
def family_id(logic_type: str, direction: str, source_hash: str) -> str:
    """Deterministic family identifier from logic + direction + source code hash."""
    return hash12(normalize_text(logic_type), normalize_text(direction), source_hash)
```

`source_hash` = `hash12` of the strategy's Python source file content, computed at `qw record`
time. If a parameter changes (RSI 14 → RSI 20), `source_hash` is unchanged. If the logic
changes (RSI → Bollinger Bands), `source_hash` changes and a new family is born.

**Schema change:** `family_id: str` added to the `Strategy` node in `models.py` and persisted
via `cypher.py`. Because `strategy_id` already encodes `instrument + timeframe + direction +
logic_type`, the `family_id` is a **cross-instrument** grouping key: same family, different
`strategy_id` values.

**Open decision:** Is `source_hash` a property on `Strategy`, or a separate `LogicBlob` node
with a `IMPLEMENTS_LOGIC` edge? Property approach is V1-compatible. Node approach supports
"show me all strategies that implemented this logic." Recommend property for V1; node for V2
only if the query need is demonstrated.

### 2. Significance Gate (Ingestion Filter for `grid_csv`)

`CSVParser.parse()` currently returns a `ResearchArtifact` containing all rows. The Curator
adds a filter step **after parsing, before persisting**. It selects the instructive runs from
the full parse result.

**Selection criteria (applied in order, non-overlapping):**

| Tier | Criterion | Default N |
|---|---|---|
| Performance | Top N rows by `sharpe` | 5 |
| Risk boundary | Bottom N rows by `max_drawdown` (worst drawdown) | 2 |
| Provenance | Rows whose `run_id` matches a known champion's `pivot_from_run_id` | all |
| Manual override | Rows flagged via `--significant <run_id>` at `qw record` time | all |

Rows not selected are **not discarded** — they are rolled up into a `RunStatsSummary` node
(see §3). The `--all` flag on `qw record --kind grid_csv` bypasses the gate entirely (existing
behavior preserved for controlled ingest).

**Implementation location:** A new `research/graph/curator.py` module with a
`apply_significance_gate(artifact, top_n_sharpe, bottom_n_drawdown, pinned_run_ids)` function
that takes a `ResearchArtifact` and returns `(selected: ResearchArtifact, summary: RunStatsSummary)`.
This keeps `parsers.py` (parsing) and `store.py` (persistence) single-responsibility.

**`baseline_csv` is unaffected.** The gate applies only to `grid_csv`. A baseline run represents
a deliberate single configuration, not a sweep.

### 3. `RunStatsSummary` Node

Aggregate record for runs that did not pass the significance gate.

**Proposed schema:**
```
RunStatsSummary {
    summary_id: str          # hash12(strategy_id, artifact_path, artifact_mtime)
    strategy_id: str
    artifact_path: str
    total_run_count: int
    selected_run_count: int
    rolled_up_run_count: int
    sharpe_mean: float
    sharpe_max: float
    sharpe_min: float
    max_drawdown_worst: float
    ingested_at: datetime
}
```

Edge: `(Strategy)-[:HAS_RUN_SUMMARY]->(RunStatsSummary)`

MCP reads `RunStatsSummary` via a new `get_run_stats_summary_v1(strategy_id)` view function.
This is the bounded alternative to listing all runs — one aggregate node per grid-sweep instead
of 1,000 `Run` nodes.

### 4. Lifecycle: Orphaned vs. Aborted

**Orphaned (default):** A strategy exists in the graph, has runs, has no champion. This is
active research. No schema change — current state is already "orphaned" by definition.

**Aborted (explicit terminal state):** The researcher has concluded the family has no viable
edge. A new `qw abort` command marks the `Strategy` node:

```
Strategy.status = "ABORTED"
Strategy.abort_reason = "Low edge stability across instruments"
Strategy.aborted_at = datetime()
```

This is a `SET` operation in Neo4j — no node deletion, no data loss. The abort reason is
surfaced to MCP via `get_strategy_summary_v1` (already returns strategy metadata) once
the `status` and `abort_reason` fields are added to the `StrategySummaryV1` DTO.

**`qw abort` CLI interface:**
```zsh
qw abort --strategy <strategy_id> --reason "Low edge stability across instruments"
```

`--reason` is mandatory. An empty reason string is rejected at the CLI layer.

**Cross-instrument abort propagation:** When `ES-1H-bear-rsi-reversion` is aborted, it does
**not** automatically propagate to `NQ-1H-bear-rsi-reversion`. Same `family_id`, separate
strategy lifecycle. The correlation query (`get_cross_artifact_correlation_v1`) will expose
the sibling's aborted status as a flag — the researcher decides whether to abort the sibling.
This avoids silent automated state changes. (See Open Questions.)

---

## Acceptance Criteria

- [x] `family_id(logic_type, direction, source_hash)` function added to `research/graph/ids.py`.
      `source_hash` is `hash12` of the strategy source file bytes. Determinism test: same file
      content → same `family_id` regardless of filename or path.
- [x] `Strategy` model in `research/graph/models.py` gains `family_id: str | None = None` field.
      `cypher.py` `CSV_INGEST_QUERY` persists `family_id` on `Strategy` node MERGE.
- [x] `qw record --kind grid_csv` applies the significance gate by default (top-5 Sharpe, bottom-2
      drawdown). `--all` flag bypasses it. Unit test: a 1,000-row `ResearchArtifact` passes through
      the gate and produces ≤ 10 selected runs + 1 `RunStatsSummary`.
- [x] `RunStatsSummary` node type defined in `models.py` with `HAS_RUN_SUMMARY` edge. `store.py`
      persists the summary node in `_persist_csv`. `cypher.py` contains `RUN_STATS_SUMMARY_QUERY`.
- [x] `qw abort --strategy <id> --reason <str>` command implemented in `cli.py`. Rejects empty
      reason. Sets `status`, `abort_reason`, `aborted_at` on the `Strategy` node. Requires the
      strategy to exist in the graph; returns a non-zero exit code if not found.
- [x] `get_strategy_summary_v1` DTO (`StrategySummaryV1` in `query_models.py`) gains
      `status: str | None` and `abort_reason: str | None`. Query updated to return these fields.
      Existing callers (MCP adapter, preset layer) are unaffected — new fields default to `None`.
- [x] `get_cross_artifact_correlation_v1` updated to filter by `family_id` instead of
      `logic_type + direction`. `CrossArtifactRowV1` DTO gains `family_id: str | None` field.
      V1 fallback: if `family_id` is `None` on any strategy node, fall back to `logic_type + direction`
      for that query.
- [x] `docs/graph_v1_contract.md` updated: `Strategy` node schema gains `family_id`, `status`,
      `abort_reason`, `aborted_at`. `RunStatsSummary` node type documented with edge
      `HAS_RUN_SUMMARY`. Significance gate rules documented under § Ingestion.

---

## Repo Touchpoints

| File | Change |
|---|---|
| `research/graph/ids.py` | Add `family_id(logic_type, direction, source_hash)` |
| `research/graph/models.py` | Add `family_id` to `Strategy`; add `RunStatsSummary` model; add `status`, `abort_reason`, `aborted_at` to `Strategy` (optional fields, default `None`) |
| `research/graph/curator.py` | **New file.** `apply_significance_gate()` — pure function, no I/O |
| `research/graph/parsers.py` | `CSVParser` unchanged. Significance gate called in `cli.py` after parse |
| `research/graph/cypher.py` | Update `CSV_INGEST_QUERY` to include `family_id`; add `RUN_STATS_SUMMARY_QUERY`; add `ABORT_STRATEGY_QUERY` |
| `research/graph/store.py` | `_persist_csv` accepts optional `RunStatsSummary` and persists it; add `abort_strategy(strategy_id, reason)` method |
| `research/graph/cli.py` | Update `cmd_record` to call curator gate for `grid_csv`; add `qw abort` subcommand + `cmd_abort` handler |
| `research/graph/query.py` | Update `GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER` to use `family_id`; update `get_strategy_summary_v1` to return `status` + `abort_reason`; add `get_run_stats_summary_v1` |
| `research/graph/query_models.py` | Add `family_id`, `status`, `abort_reason` to `StrategySummaryV1`; add `RunStatsSummaryV1` DTO; update `CrossArtifactRowV1` to include `family_id` |
| `docs/graph_v1_contract.md` | Schema delta: `Strategy`, `RunStatsSummary` node types; ingestion rules; `HAS_RUN_SUMMARY` edge |
| `tests/unit/test_curator.py` | **New file.** Gate selection logic, boundary conditions, `--all` passthrough |
| `tests/unit/test_ids.py` | Add `family_id` determinism tests |
| `tests/unit/test_qw_abort.py` | **New file.** CLI abort command — valid, missing reason, unknown strategy |

---

## Definition of Done

- [ ] All new unit tests pass. Existing tests (`test_mcp_adapter.py`, `test_qw_query.py`,
      `test_lineage_queries.py`) remain green — no regressions.
- [ ] A 1,000-row grid CSV `qw record` run produces ≤ 10 `Run` nodes and 1 `RunStatsSummary`
      node for the strategy (verifiable via `qw query --name strategy_lineage`).
- [ ] `qw abort --strategy <id> --reason "..."` sets `status=ABORTED` on the neo4j `Strategy`
      node. `get_strategy_summary_v1` returns `status="ABORTED"` and `abort_reason` in response.
- [ ] `get_cross_artifact_correlation_v1` returns results grouped by `family_id` when the field
      is populated; falls back to `logic_type + direction` otherwise.
- [ ] Story marked CLOSED after test suite passes and `docs/graph_v1_contract.md` is updated.

---

## Dependencies

- **Depends on (CLOSED):** `spike_lean_neighborhood_optimization.md` — V1 `max_runs` cap is in
  place; this story removes the need to rely on it long-term by reducing the run count at ingest.
- **Depends on (CLOSED):** Story 0 schema mapping, Story 1 query layer, Story 3 MCP adapter —
  all read paths are stable; this story extends write paths only.
- **Enables:** `get_cross_artifact_correlation_v1` becomes trustworthy at scale (currently
  groups by `logic_type + direction`, which becomes ambiguous at 10+ strategies).
- **Enables:** Epic 3 — MCP can now answer "why was this family abandoned?" via `abort_reason`.

---

## Open Questions

1. **`source_hash` location:** Property on `Strategy` node vs. separate `LogicBlob` node with
   `IMPLEMENTS_LOGIC` edge. Recommend property for V1; revisit if we need "show all strategies
   with this logic version."

2. **Abort propagation:** When `ES-1H-bear-rsi-reversion` is aborted, should `NQ-1H-bear-rsi-reversion`
   automatically gain `status=CAUTION`? Current design: no propagation — `get_cross_artifact_correlation_v1`
   exposes the sibling's status; researcher decides. Revisit if false negatives accumulate.

3. **Top-N defaults:** Are `top_n_sharpe=5` and `bottom_n_drawdown=2` the right defaults, or
   should they be configurable via `qw record --top-n 10`? Recommend hard defaults in V1;
   add `--top-n` and `--bottom-n` flags only if research workflows demonstrate a need.

4. **`--all` flag semantics for reingestion:** If a grid CSV was previously ingested with `--all`
   and is re-ingested with the gate active, should existing unselected `Run` nodes be deleted
   or orphaned? Recommend: gate applies only to new `MERGE` operations; no retroactive deletion.

5. **`RunStatsSummary` uniqueness:** One summary per `(strategy_id, artifact_path)` pair, or
   per `artifact_mtime`? If the same CSV is re-ingested after modification, should the summary
   be updated (SET) or versioned? Recommend: `MERGE` on `summary_id = hash12(strategy_id,
   artifact_path, artifact_mtime)` — updates naturally when the file changes.
