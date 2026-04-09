# Story 3 — Cross-Instrument Aggregator

## ID
QWS-0503

## Status
draft

## Summary
Add a `compare_strategy_performance` query preset that aggregates champion metrics by
`logic_type` across all instruments, showing IS and OOS Sharpe side-by-side. Answers
"which strategy types are universal vs. instrument-specific?"

## Problem
Strategies are queried in isolation. There is no single view that compares how the same
logic type (e.g., `liquidity-sweep`, `mars`) performs across CL, ES, NQ, BTC. The
researcher must issue separate `run_history` queries per strategy and mentally join them.

## Dependencies
- **QWS-0501** (family_id population) must be CLOSED first — `family_id` is the grouping
  key for strategy logic. Without it this query returns no cross-instrument groupings.
- **QWS-0402C** (OOS Sharpe amendment) must be CLOSED first — stores `metrics_oos_sharpe`
  on Champion at `qw record --oos --sharpe` time. Without it the `oos_sharpe` column is
  permanently null.

## Goal
```zsh
qw query --name compare_strategy_performance
# Optional: filter to one logic type
qw query --name compare_strategy_performance --param logic_type=liquidity-sweep
```

Output columns per row: `logic_type`, `direction`, `instrument`, `timeframe`,
`champion_id`, `is_sharpe`, `oos_sharpe` (nullable), `win_rate`, `total_trades`,
`oos_status`, `freeze_date`.

Ordered by `logic_type`, then `is_sharpe` descending — so the best instrument for each
logic type floats to the top within its group.

## Cypher sketch
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE s.family_id IS NOT NULL
RETURN s.logic_type        AS logic_type,
       s.direction         AS direction,
       s.instrument        AS instrument,
       s.timeframe         AS timeframe,
       ch.champion_id      AS champion_id,
       ch.metrics_sharpe   AS is_sharpe,
       ch.metrics_oos_sharpe AS oos_sharpe,
       ch.metrics_win_rate AS win_rate,
       ch.metrics_total_trades AS total_trades,
       ch.oos_status       AS oos_status,
       toString(ch.freeze_date) AS freeze_date
ORDER BY s.logic_type, ch.metrics_sharpe DESC
```

Note: `ch.metrics_oos_sharpe` is populated by QWS-0402C (`qw record --oos --sharpe <float>`).
This story is blocked on QWS-0402C CLOSED — the column should be non-null before shipping.

## Repo Touchpoints
- `qws_graph/research/graph/query_presets.py` — `compare_strategy_performance` preset
- `qws_graph/research/graph/query.py` — Cypher for preset
- `qws_graph/docs/qws_graph_runbook.md` — Day-1 entry for `compare_strategy_performance`
- `qws_graph/tests/unit/test_qw_query.py` — extend with multi-instrument mock data tests — new tests

## In Scope
- `compare_strategy_performance` preset in `query_presets.py` and `query.py`
- Optional `logic_type` param to narrow results
- Unit test using mock session
- Runbook Day-1 section entry

## Out of Scope
- Instrument metadata nodes (tick_size, contract_value — must NOT come from graph at run time)
- Heatmap or chart rendering
- Strategies without a current Champion (run history comparison without promotion is
  a separate analytics question)

## Acceptance Criteria
- [ ] `qw query --name compare_strategy_performance` returns rows grouped by `logic_type`
  across instruments after at least two different instruments have champions.
- [ ] `--param logic_type=liquidity-sweep` filters to that logic type only.
- [ ] Strategies with `family_id IS NULL` are excluded from results (not an error).
- [ ] `oos_sharpe` column is present but nullable.
- [ ] Unit test covers multi-instrument mock data and single-instrument edge case.

## Definition of Done
- [ ] Preset implemented and tested.
- [ ] Runbook updated.
- [ ] Story marked CLOSED.
