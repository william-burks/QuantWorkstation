# Story 2 — Champion Query Presets

## ID
# QWS-0302

## Status
CLOSED

## Priority
P2 — Observability. The Champion nodes now store flat metric properties (`metrics_sharpe`,
`metrics_return`, `tier`, etc.) but no presets expose them as queryable surfaces. Three
analytical presets are needed to make champion data usable from the CLI and from direct
Cypher without requiring the caller to know the graph topology.

## Summary
Add three presets to `query_presets.py` backed by new view functions in `query.py`:

1. **`portfolio_alpha`** — aggregate return and Sharpe across all professional/institutional Champions.
2. **`fragility_report`** — surface Champions with regime-sensitivity fragility flags.
3. **`trace_champion`** — trace the Strategy→Champion lineage for a specific champion_id.

## Correct Graph Topology

```
Strategy -[:PRODUCED_CHAMPION]-> Champion
Strategy -[:HAS_RUN]-> Run
Champion -[:PIVOTED_FROM]-> Run   (optional — only when pivot_from_run_id is set)
```

`Run -[:PRODUCED_CHAMPION]-> Champion` does **not** exist. The Lineage Trace query anchors
on Strategy, not Run.

## Proposed Design

### `portfolio_alpha`
```cypher
MATCH (ch:Champion)
WHERE ch.tier IN ['professional', 'institutional']
WITH count(ch) AS champion_count,
     sum(ch.metrics_return) AS total_return,
     avg(ch.metrics_sharpe) AS avg_sharpe,
     collect(ch.strategy_id) AS strategies
RETURN {
  champion_count: champion_count,
  total_return: total_return,
  avg_sharpe: avg_sharpe,
  strategies: strategies
} AS result
```

CLI: `qw query --name portfolio_alpha`

### `fragility_report`
```cypher
MATCH (ch:Champion)
WHERE any(f IN ch.fragilities WHERE toLower(f) CONTAINS 'regime')
RETURN {
  strategy_id: ch.strategy_id,
  champion_id: ch.champion_id,
  tier: ch.tier,
  oos_status: ch.oos_status,
  fragilities: ch.fragilities
} AS result
ORDER BY ch.strategy_id ASC
```

CLI: `qw query --name fragility_report`

### `trace_champion`
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion {champion_id: $champion_id})
OPTIONAL MATCH (ch)-[:PIVOTED_FROM]->(r:Run)
RETURN {
  strategy_id: s.strategy_id,
  champion_id: ch.champion_id,
  artifact_path: ch.artifact_path,
  tier: ch.tier,
  metrics_sharpe: ch.metrics_sharpe,
  metrics_return: ch.metrics_return,
  pivot_run_id: r.run_id
} AS result
```

CLI: `qw query --name trace_champion --param champion_id=<id>`

## In Scope
- `qws_graph/research/graph/query.py` — 3 Cypher constants, 3 view functions, registry + `__all__` updates
- `qws_graph/research/graph/query_presets.py` — 3 `PresetSpec` entries + `run_preset` dispatch
- `qws_graph/tests/unit/test_qw_query.py` — extend `FakeGraphQueryService`, add routing tests

## Out of Scope
- New Pydantic DTOs for aggregate results — plain dicts are sufficient for these analytical presets.
- Changes to the CLI `cmd_query` surface — presets route through the existing dispatch.

## Repo Touchpoints
- `qws_graph/research/graph/query.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/tests/unit/test_qw_query.py`

## Acceptance Criteria
- [x] `qw query --name portfolio_alpha` returns `champion_count`, `total_return`, `avg_sharpe`, `strategies`.
- [x] `qw query --name fragility_report` returns champions whose fragilities contain "regime".
- [x] `qw query --name trace_champion --param champion_id=<id>` returns strategy_id, artifact_path, tier, metrics.
- [x] Unknown preset names still raise `ValueError` with the full available list.
- [x] Unit tests cover routing for all three new presets via `FakeGraphQueryService`.

## Definition of Done
- [x] 3 Cypher constants added to `query.py`.
- [x] 3 view functions added; registered in `QUERY_VIEW_REGISTRY` and `__all__`.
- [x] 3 `GraphQueryService` delegation methods added.
- [x] 3 `PresetSpec` entries in `PRESET_CATALOG`; `run_preset` dispatch handles all three.
- [x] Unit tests added and passing.
