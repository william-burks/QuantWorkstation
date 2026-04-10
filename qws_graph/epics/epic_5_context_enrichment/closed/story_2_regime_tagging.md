# Story 2 — Regime Tagging

## ID
QWS-0502

## Status
CLOSED

## Summary
Add an optional `--regime` flag to `qw record` that stores a regime label as a string
property on ingested Run nodes. No new node types. No automated tagging in scope.
Enables regime-conditional queries immediately.

## Problem
Every Run node exists in a market context vacuum. A strategy might look like a champion
because it was backtested entirely during a high-volatility trending regime — and fail
silently in a grinding sideways market. The graph has no way to express this.

The query "show me champions that passed OOS during high-volatility periods" is
currently unanswerable because `regime` was never recorded.

## Goal
After this story, the operator can tag a run at ingest time:
```zsh
qw record --file results.csv --kind baseline_csv --regime high_vol
qw record --file results.csv --kind baseline_csv --regime trend_up
qw record --bundle <dir> --regime mean_reverting
```

And query by it:
```zsh
qw query --name runs_by_regime --param regime=high_vol
```

## Design

### `:Regime` node
One node per distinct regime label (e.g., `high_vol`, `trend_down`). Keyed on
`regime_id` — the raw string from `--regime`. Created on first use; merged
idempotently on subsequent ingests. Carries `created_at` and `updated_at`.

### `IN_REGIME` edge
`(Run)-[:IN_REGIME]->(Regime)`. Created when `--regime` is supplied. Absent when
no regime was tagged. Allows graph traversal and aggregation by regime without
reading Run properties.

### `regime` property on `:Run`
Denormalized copy of the regime label stored directly on the Run node for
convenience (avoids traversal for simple lookups). Absent (NULL) when no regime
was tagged.

### CLI flag
`--regime <string>` added to `qw record`. Applied to all Run nodes persisted in that
ingest call. Creates/merges the Regime node and IN_REGIME edge for each persisted run.
Absent when not passed — both Run.regime and the IN_REGIME edge are omitted.

### Query preset: `runs_by_regime`
```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)-[:IN_REGIME]->(reg:Regime {regime_id: $regime})
RETURN r.run_id, s.strategy_id, r.sharpe, r.total_trades,
       reg.regime_id AS regime, toString(r.ingested_at) AS ingested_at
ORDER BY r.sharpe DESC
```
Param: `regime` (required).

### `regime` on Champion queries
The existing `trace_champion` and `strategy_lineage` presets traverse
`(Champion)-[:PIVOTED_FROM]->(Run)`. After this story, callers can traverse
`(Run)-[:IN_REGIME]->(Regime)` in those results to see what market context the
pivot run lived in. No preset changes needed — the data is already reachable.

## In Scope
- `--regime` optional flag on `qw record` in `cli.py`
- `:Regime` node merged idempotently per distinct label via `store.py`
- `IN_REGIME` edge created per persisted Run when `--regime` is supplied
- `regime` property also set on Run node (denormalized convenience copy)
- `runs_by_regime` query preset in `query_presets.py` and `query.py`
- `regime` and `Regime` node added to `data_dictionary.yaml`
- Demo seed updated to create Regime nodes + IN_REGIME edges
- Runbook Day-1 section updated with regime conventions and example queries
- Unit tests for CLI flag parsing and query preset

## Out of Scope
- Automated regime detection (ATR-slope, MA-based tagging) — that is a research analytics
  problem; this story handles only explicit operator-supplied labels
- `volatility_state` / `trend_state` sub-properties on Regime node — stored as opaque
  regime_id for this story; decomposition deferred to a future story
- Validation of regime string values (researcher-defined; no enum)
- Backfilling regime on existing Run nodes

## Acceptance Criteria
- [x] `qw record --file results.csv --kind baseline_csv --regime high_vol` creates a
  `Regime {regime_id: "high_vol"}` node, an `IN_REGIME` edge from each persisted Run
  to that Regime node, and sets `r.regime = "high_vol"` on each Run.
- [x] `qw record` without `--regime` leaves `r.regime` absent (not empty string) and
  creates no Regime node or IN_REGIME edge.
- [x] `qw query --name runs_by_regime --param regime=high_vol` returns matching runs
  (traversing via IN_REGIME).
- [x] `qw query --name runs_by_regime` without `--param regime` returns a clear error.
- [x] `data_dictionary.yaml` documents `Regime` node and `IN_REGIME` relationship.
- [x] Runbook documents at least 6 suggested regime label conventions.

## Definition of Done
- [x] CLI flag, Regime node, IN_REGIME edge, store write, query preset implemented and tested.
- [x] Demo seed updated with Regime nodes + IN_REGIME edges.
- [x] Docs updated (data_dictionary, runbook).
- [x] Story marked CLOSED.
