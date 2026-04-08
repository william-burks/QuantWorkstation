# Story 3 — Workflow Query Presets

## ID
QWS-0406

## Status
CLOSED

## Summary
Deliver the operational query surface for Epic 4: new presets that answer "what do I need
to do next?", decommission legacy presets that clutter the MCP interface, and add an aborted
strategy surface. Implemented in two phases — Phase A ships independently; Phase B is gated
on QWS-0407 (significance gate properties).

## Problem
The current query presets answer historical and analytical questions (`recent_champions`,
`run_history`, `portfolio_alpha`). None answer the immediate operational question:
**"What do I need to do next?"**

After any pipeline run, the operator has to mentally join:
- Which champions have `oos_pending` status
- Which runs cleared the professional tier but haven't been promoted
- Which strategies were aborted and why

These are graph queries, not file reads. The data is already there. Additionally, four legacy
presets (`rank_by_evidence`, `trace_champion`, `fragility_report`, `staleness_report`) are
either redundant, stale, or low-value and should be removed from the MCP surface.

## Goal

### Phase A — Ships independently (no external blockers)
1. `list_oos_pending` — Champions waiting for OOS validation
2. `list_aborted` — Aborted strategies with cause-of-death
3. Deprecate `rank_by_evidence`, `trace_champion` (redundant duplicates — safe to remove now)
4. Amend all Strategy traversals: add `WHERE s.status <> 'ABORTED'`

### Phase C — Deferred Deprecations (gated on downstream stories)
- `staleness_report` — defer removal until QWS-0402 is CLOSED (QWS-0402 AC 6 still calls this preset)
- `fragility_report` — defer removal until QWS-0801 (`former_champions`) and QWS-0503 (`regime_performance`) are CLOSED; removing before replacements exist leaves no fragility surface in the MCP interface

### Phase B — Gated on QWS-0407 (significance gate properties)
5. `promotion_candidates` — Runs meeting dual-hurdle gate, not yet promoted

---

## Phase A Presets

### `list_oos_pending`
Returns champions with `oos_status = oos_pending`, oldest first.

```zsh
qw query --name list_oos_pending
```

Output per row: `champion_id`, `strategy_id`, `freeze_date`, `metrics_sharpe`,
`metrics_total_trades`, `days_pending` (computed from today).

```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE ch.oos_status = 'oos_pending'
  AND s.status <> 'ABORTED'
RETURN ch.champion_id        AS champion_id,
       ch.strategy_id        AS strategy_id,
       toString(ch.freeze_date) AS freeze_date,
       ch.metrics_sharpe     AS metrics_sharpe,
       ch.metrics_total_trades AS metrics_total_trades,
       duration.between(ch.freeze_date, date()).days AS days_pending
ORDER BY ch.freeze_date ASC
```

### `list_aborted`
Returns all strategies where `status = ABORTED`, with cause-of-death. Used by the LLM
before suggesting any new strategy to prevent re-treading a killed path.

```zsh
qw query --name list_aborted
```

Output per row: `strategy_id`, `instrument`, `direction`, `logic_type`, `abort_reason`,
`aborted_at`.

```cypher
MATCH (s:Strategy)
WHERE s.status = 'ABORTED'
RETURN s.strategy_id  AS strategy_id,
       s.instrument   AS instrument,
       s.direction    AS direction,
       s.logic_type   AS logic_type,
       s.abort_reason AS abort_reason,
       toString(s.aborted_at) AS aborted_at
ORDER BY s.aborted_at DESC
```

### Strategy traversal amendment
All existing presets that traverse Strategy nodes add `WHERE s.status <> 'ABORTED'` to
their Cypher. Affected presets: `recent_champions`, `strategy_lineage`, `run_history`,
`downstream_champions`, `cross_artifact_correlation`, `portfolio_alpha`,
`instrument_concentration`, `staleness_report` (before deprecation).

---

## Phase A Deprecations

Remove from `query_presets.py` and `query.py`. Raise `PresetNotFound` (existing behaviour)
if called after removal.

| Preset | Reason |
|---|---|
| `rank_by_evidence` | Redundant — duplicate of `run_history` |
| `trace_champion` | Redundant — duplicate of `downstream_champions` |

## Phase C — Deferred Deprecations

Do **not** remove these in Phase A. Removal is gated on downstream stories.

| Preset | Removal Gate | Reason for Deferral |
|---|---|---|
| `staleness_report` | QWS-0402 CLOSED | Remove alongside the OOS lifecycle story to minimize operator confusion during the transition |
| `fragility_report` | QWS-0801 + QWS-0503 CLOSED | Replacement signals (`former_champions`, `regime_performance`) don't exist yet; removing leaves no fragility surface in the MCP interface |

---

## Phase B Preset (gated on QWS-0407)

### `promotion_candidates`
Returns Run nodes that pass the dual-hurdle significance gate, meet the professional tier,
and have no Champion node linked. Ordered by evidence score descending.

```zsh
qw query --name promotion_candidates
qw query --name promotion_candidates --param min_sharpe=2.5
```

Output per row: `run_id`, `strategy_id`, `sharpe`, `tier`, `profit_factor`, `total_trades`,
`active_window_frequency`, `duty_cycle`, `evidence_score`, `ingested_at`.

**Tier is mandatory output** — differentiates Professional from Institutional before the LLM
recommends promotion.

```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)
WHERE s.status <> 'ABORTED'
  AND r.sharpe >= $min_sharpe
  AND r.profit_factor >= $min_profit_factor
  AND r.total_trades >= 30
  AND r.active_window_frequency >= 0.06
  AND NOT EXISTS { MATCH (ch:Champion)-[:PIVOTED_FROM]->(r) }
WITH r, s, (r.sharpe * sqrt(toFloat(r.total_trades))) AS ev
ORDER BY ev DESC
RETURN r.run_id                    AS run_id,
       s.strategy_id               AS strategy_id,
       r.sharpe                    AS sharpe,
       r.tier                      AS tier,
       r.profit_factor             AS profit_factor,
       r.total_trades              AS total_trades,
       r.active_window_frequency   AS active_window_frequency,
       r.duty_cycle                AS duty_cycle,
       ev                         AS evidence_score,
       toString(r.ingested_at)    AS ingested_at
```

Default params: `min_sharpe=2.0`, `min_profit_factor=1.3`.
Note: `min_trades=30` and `min_frequency=0.06` are hardcoded gates, not overridable params.

**Phase B cannot ship until `r.active_window_frequency` and `r.duty_cycle` are populated
at ingest time. See QWS-0407.**

---

## In Scope
- `qws_graph/research/graph/query.py` — new Cypher constants, deprecated constants removed
- `qws_graph/research/graph/query_presets.py` — new registrations, deprecated registrations removed
- `WHERE s.status <> 'ABORTED'` added to all affected existing presets
- Unit tests following the pattern in `test_qw_query.py`
- `qws_graph/docs/qws_graph_runbook.md` Day-1 Operations updated

## Out of Scope
- MCP tool wrappers (follow automatically from preset registration)
- OOS pass/fail write path (that's QWS-0402)
- `active_window_frequency` / `duty_cycle` computation (that's QWS-0407)
- `former_champions`, `regime_performance` presets (future stories)

## Repo Touchpoints
- `qws_graph/research/graph/query.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/qws_graph_runbook.md`
- `qws_graph/tests/unit/test_qw_query.py`

## Acceptance Criteria

### Phase A
- [x] `qw query --name list_oos_pending` exits `0`; returns Champions with `oos_status = oos_pending`.
- [x] `qw query --name list_aborted` exits `0`; returns Strategies with `status = ABORTED` including `abort_reason`.
- [x] `qw query --name rank_by_evidence` raises `PresetNotFound`.
- [x] `qw query --name trace_champion` raises `PresetNotFound`.
- [x] `qw query --name fragility_report` still returns results (not removed in Phase A).
- [x] `qw query --name staleness_report` still returns results (not removed in Phase A).
- [x] `recent_champions` and `strategy_lineage` exclude ABORTED strategies.
- [x] Both Phase A presets return empty list gracefully when no matching data exists.

### Phase B (after QWS-0407)
- [x] `qw query --name promotion_candidates` exits `0`; excludes runs with `total_trades < 30`.
- [x] `qw query --name promotion_candidates` excludes runs with `active_window_frequency < 0.06`.
- [x] Output includes `tier` column (Professional / Institutional).
- [x] Output includes `active_window_frequency` and `duty_cycle` columns.
- [x] `qw query --name promotion_candidates --param min_sharpe=2.5` filters correctly.
- [x] A run with a linked Champion via `PIVOTED_FROM` does not appear in output.
- [x] Empty list returned gracefully when no candidates exist.

## Definition of Done
- [x] Phase A implemented and tested.
- [x] Phase B implemented and tested (after QWS-0407 complete).
- [x] Runbook Day-1 Operations section updated.
- [x] Story marked CLOSED.
