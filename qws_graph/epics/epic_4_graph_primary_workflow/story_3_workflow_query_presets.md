# Story 3 — Workflow Query Presets

## ID
QWS-0406

## Status
draft

## Summary
Add two `qw query` presets that surface actionable workflow state: what needs OOS
validation and what recently cleared promotion thresholds. These make the graph useful
for decision-making without touching any write paths.

## Problem
The current query presets answer historical and analytical questions (`recent_champions`,
`run_history`, `portfolio_alpha`). None answer the immediate operational question:
**"What do I need to do next?"**

After any pipeline run, the operator has to mentally join:
- Which champions have `oos_pending` status
- Which runs cleared the professional tier but haven't been promoted
- How long any of this has been sitting

These are graph queries, not file reads. The data is already there.

## Goal
Two new presets:

### `list_oos_pending`
Returns champions that still have `oos_status = oos_pending`, ordered by `freeze_date`
ascending (oldest first — longest-waiting first).

```zsh
qw query --name list_oos_pending
```

Output per row: `champion_id`, `strategy_id`, `freeze_date`, `metrics_sharpe`,
`metrics_total_trades`, `days_pending` (computed from today).

### `promotion_candidates`
Returns Run nodes that clear the `professional` tier thresholds and have no Champion node
linked via `PIVOTED_FROM`. Ordered by evidence score descending.

```zsh
qw query --name promotion_candidates
```

Output per row: `run_id`, `strategy_id`, `sharpe`, `profit_factor`, `total_trades`,
`evidence_score`, `ingested_at`.

Note: this preset queries the graph state at query time, not at ingest time. It surfaces
runs that were ingested before Story 2 (promotion alerts) existed, and remains useful as
a periodic audit even after Story 2 is live.

## In Scope
- `qws_graph/research/graph/query_presets.py` — two new preset registrations
- `qws_graph/research/graph/query.py` — two new Cypher constants
- Unit tests following the pattern in `test_qw_query.py`
- `qws_graph/docs/qws_graph_runbook.md` Day-1 Operations section updated with both presets

## Out of Scope
- Modifying existing presets
- MCP tool wrappers (those follow automatically from the preset registration)
- Defining OOS thresholds or pass/fail criteria (that's Story 1)

## Repo Touchpoints
- `qws_graph/research/graph/query.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/qws_graph_runbook.md`
- `qws_graph/tests/unit/test_qw_query.py`

## Cypher sketches

### `list_oos_pending`
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE ch.oos_status = 'oos_pending'
RETURN ch.champion_id AS champion_id,
       ch.strategy_id AS strategy_id,
       toString(ch.freeze_date) AS freeze_date,
       ch.metrics_sharpe AS metrics_sharpe,
       ch.metrics_total_trades AS metrics_total_trades,
       duration.between(ch.freeze_date, date()).days AS days_pending
ORDER BY ch.freeze_date ASC
```

### `promotion_candidates`
```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)
WHERE r.sharpe >= $min_sharpe
  AND r.profit_factor >= $min_profit_factor
  AND r.total_trades >= $min_trades
  AND NOT EXISTS { MATCH (ch:Champion)-[:PIVOTED_FROM]->(r) }
WITH r, s, (r.sharpe * sqrt(toFloat(r.total_trades))) AS ev
ORDER BY ev DESC
RETURN r.run_id AS run_id,
       s.strategy_id AS strategy_id,
       r.sharpe AS sharpe,
       r.profit_factor AS profit_factor,
       r.total_trades AS total_trades,
       ev AS evidence_score,
       toString(r.ingested_at) AS ingested_at
```
Default params: `min_sharpe=1.5`, `min_profit_factor=1.75`, `min_trades=30`
(matching `standards.py` `professional` tier).

## Acceptance Criteria
- [ ] `qw query --name list_oos_pending` exits `0` and returns champions with
  `oos_status = oos_pending`.
- [ ] `qw query --name promotion_candidates` exits `0` and returns runs that clear
  thresholds with no Champion linked.
- [ ] `qw query --name promotion_candidates --param min_sharpe=2.5` filters correctly.
- [ ] A run that has a Champion linked via `PIVOTED_FROM` does not appear in
  `promotion_candidates`.
- [ ] Both presets return empty list gracefully when no matching data exists.
- [ ] Both presets are registered in the MCP adapter automatically (no extra wiring needed).
- [ ] Unit tests follow existing `test_qw_query.py` pattern.

## Definition of Done
- [ ] Both presets implemented and tested.
- [ ] Runbook Day-1 Operations section updated.
- [ ] Story marked CLOSED.
