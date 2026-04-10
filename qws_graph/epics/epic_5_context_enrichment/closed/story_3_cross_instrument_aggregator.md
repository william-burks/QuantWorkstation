# Story 3 — Cross-Instrument Aggregator (regime_performance)

## ID
QWS-0503

## Status
CLOSED

## Summary
Add a `regime_performance` query preset that aggregates run metrics by regime across all
strategies, showing best Sharpe per regime and a Regime Diversity Score. Answers
"which strategies are regime-robust vs. regime specialists (fragility flag)?"

## Problem
Runs are tagged with a regime label (via `IN_REGIME` edge, QWS-0502) but there is no
aggregated view. The researcher must query `runs_by_regime` with each label separately
and mentally compute per-strategy coverage. There is no surface for the Regime Diversity
Score — the key fragility signal defined in PROVENANCE_ENGINE.md.

## Dependencies
- **QWS-0501** (family_id population) — CLOSED
- **QWS-0402C** (OOS Sharpe amendment) — CLOSED
- **QWS-0502** (Regime tagging / IN_REGIME edge) — CLOSED

## Goal
```zsh
qw query --name regime_performance
# Optional: filter to one strategy
qw query --name regime_performance --param strategy_id=<id>
```

Output columns per row: `strategy_id`, `instrument`, `family_id`, `regime`,
`best_sharpe`, `run_count`, `diversity_score`, `fragility_class`.

`diversity_score` = count of distinct regimes where the strategy's best Sharpe ≥ 2.0.
- Score = 1 → `fragility_class = "Regime Specialist"`
- Score ≥ 3 → `fragility_class = "Regime Robust"`
- Otherwise → `fragility_class = null`

Ordered by `strategy_id`, then `best_sharpe` descending.

## Cypher sketch
```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)-[:IN_REGIME]->(reg:Regime)
WHERE coalesce(s.status, '') <> 'ABORTED'
WITH s, reg.regime_id AS regime_id, max(r.sharpe) AS best_sharpe, count(r) AS run_count
WITH s, collect({regime_id: regime_id, sharpe: best_sharpe, runs: run_count}) AS regime_rows
WITH s, regime_rows,
     size([row IN regime_rows WHERE row.sharpe >= 2.0]) AS diversity_score
UNWIND regime_rows AS row
RETURN {
  strategy_id: s.strategy_id,
  instrument: s.instrument,
  family_id: s.family_id,
  regime: row.regime_id,
  best_sharpe: row.sharpe,
  run_count: row.runs,
  diversity_score: diversity_score,
  fragility_class: CASE
    WHEN diversity_score = 1 THEN 'Regime Specialist'
    WHEN diversity_score >= 3 THEN 'Regime Robust'
    ELSE null
  END
} AS result
ORDER BY s.strategy_id, row.sharpe DESC
```

Optional `strategy_id` param adds `AND s.strategy_id = $strategy_id` after the WHERE clause.

## Repo Touchpoints
- `qws_graph/research/graph/query.py` — `GET_REGIME_PERFORMANCE_V1_CYPHER`, `get_regime_performance_v1`, `GraphQueryService.get_regime_performance_v1`
- `qws_graph/research/graph/query_presets.py` — `regime_performance` preset in `PRESET_CATALOG` + `run_preset` routing
- `qws_graph/docs/qws_graph_runbook.md` — Day-1 entry for `regime_performance`
- `qws_graph/tests/unit/test_regime_tagging.py` — extend with `regime_performance` preset tests

## In Scope
- `regime_performance` preset in `query_presets.py` and `query.py`
- Optional `strategy_id` param to narrow results
- Regime Diversity Score and fragility_class in output
- Unit tests using mock session
- Runbook Day-1 section entry
- Remove `regime_performance` from "Not Yet Implemented" in `docs/BACKLOG_ALIGNMENT.md`

## Out of Scope
- `compare_strategy_performance` (logic_type cross-instrument view — different story)
- Heatmap or chart rendering
- Strategies without any regime-tagged runs (they simply don't appear in results)

## Acceptance Criteria
- [x] AC#1: `qw query --name regime_performance` returns rows with `strategy_id`, `regime`,
  `best_sharpe`, `run_count`, `diversity_score`, `fragility_class` for all strategies
  with regime-tagged runs.
- [x] AC#2: `--param strategy_id=<id>` filters results to that strategy only.
- [x] AC#3: A strategy with runs in only one qualifying regime (sharpe ≥ 2.0) shows
  `diversity_score=1` and `fragility_class="Regime Specialist"`.
- [x] AC#4: A strategy with qualifying runs in ≥ 3 regimes shows `fragility_class="Regime Robust"`.
- [x] AC#5: Strategies with `status = ABORTED` are excluded from results.
- [x] AC#6: Unit tests cover diversity score calculation, optional param filtering, and
  empty-result edge case.

## Definition of Done
- [x] Preset implemented and tested.
- [x] Runbook updated.
- [x] `regime_performance` removed from "Not Yet Implemented" MCP Tools in `docs/BACKLOG_ALIGNMENT.md`.
- [x] Story marked CLOSED.