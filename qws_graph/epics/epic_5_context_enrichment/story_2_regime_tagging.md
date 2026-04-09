# Story 2 — Regime Tagging

## ID
QWS-0502

## Status
READY

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

### `regime` property on `:Run`
Optional string. Stored as-is from the `--regime` flag. No enum validation at write
time — values are researcher-defined. Conventions should be documented in the runbook
(e.g., `high_vol`, `low_vol`, `trend_up`, `trend_down`, `mean_reverting`, `crisis`).

### CLI flag
`--regime <string>` added to `qw record`. Applied to all Run nodes persisted in that
ingest call. Absent when not passed (NULL on the node, not empty string).

### Query preset: `runs_by_regime`
```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)
WHERE r.regime = $regime
RETURN r.run_id, s.strategy_id, r.sharpe, r.total_trades,
       r.regime, toString(r.ingested_at) AS ingested_at
ORDER BY r.sharpe DESC
```
Param: `regime` (required).

### `regime` on Champion queries
The existing `trace_champion` and `strategy_lineage` presets traverse
`(Champion)-[:PIVOTED_FROM]->(Run)`. After this story, callers can inspect
`Run.regime` in those results to see what market context the pivot run lived in.
No preset changes needed — the data is already reachable.

## In Scope
- `--regime` optional flag on `qw record` in `cli.py`
- `regime` stored on each persisted Run node via `store.py` (passed through payload)
- `runs_by_regime` query preset in `query_presets.py` and `query.py`
- `regime` added to `data_dictionary.yaml` and `graph_v1_contract.md`
- Runbook Day-1 section updated with regime conventions and example queries
- Unit tests for CLI flag parsing and query preset

## Out of Scope
- Automated regime detection (ATR-slope, MA-based tagging) — that is a research analytics
  problem; this story handles only explicit operator-supplied labels
- `:Regime` node type (string property on Run is sufficient and simpler)
- Validation of regime string values (researcher-defined; no enum)
- Backfilling regime on existing Run nodes

## Acceptance Criteria
- [ ] `qw record --file results.csv --kind baseline_csv --regime high_vol` stores
  `r.regime = "high_vol"` on all persisted Run nodes from that ingest.
- [ ] `qw record` without `--regime` leaves `r.regime` absent (not empty string).
- [ ] `qw query --name runs_by_regime --param regime=high_vol` returns matching runs.
- [ ] `qw query --name runs_by_regime` without `--param regime` returns a clear error.
- [ ] `data_dictionary.yaml` documents `regime` as nullable string on Run.
- [ ] Runbook documents at least 6 suggested regime label conventions.

## Definition of Done
- [ ] CLI flag, store write, query preset implemented and tested.
- [ ] Docs updated (data_dictionary, runbook).
- [ ] Story marked CLOSED.
