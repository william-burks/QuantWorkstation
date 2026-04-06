# Story — Fix `was_best` Sticky Property Semantics

## Status
CLOSED — Option A implemented. `was_best` renamed to `peaked_as_best` in `store.py`,
`data_dictionary.yaml`, and `README.md`. Migration query documented below.

## Problem

`r.was_best` is set on a `:Run` node when it is displaced as the strategy's best run
by a higher-evidence run. It is never cleared. This means once a run gets `was_best=True`,
it keeps that label even after being displaced by a second, third, fourth replacement.

At any given time only one run holds the current peak — all other `was_best` nodes are
stale. A query reader seeing `was_best=True` has no way to distinguish
"most recently displaced" from "was best three promotions ago."

## Impact

Any query or UI reading `was_best` to surface "the run that just got dethroned" will
return multiple stale results instead of one. The field name implies present state but
carries only historical state after the first displacement cycle.

## Options

### Option A — Rename to `peaked_as_best` (low-effort, no semantic loss)
Rename the property to `r.peaked_as_best = True`. The new name honestly describes
the past-tense fact: this run once held the peak. No clearing logic needed.

Migration: `MATCH (r:Run) WHERE r.was_best IS NOT NULL SET r.peaked_as_best = r.was_best REMOVE r.was_best`

### Option B — Introduce `currently_displaced` (cleared on each promotion cycle)
Before setting `was_best` on the newly displaced run, clear the flag on all other
runs for the same strategy:

```cypher
MATCH (s:Strategy {strategy_id: $sid})-[:HAS_RUN]->(r:Run)
WHERE r.was_best = True
SET r.was_best = False
```

Then set `was_best = True` only on the run being displaced now.

This makes the flag instantaneous: exactly one run per strategy is `was_best=True`
at any time — the one displaced by the most recent promotion.

## Recommendation

Option B if "most recently displaced" is a query we want to support.
Option A if the flag is purely archival / audit trail.

Current code in `store.py` writes `r.was_best = True` at displacement time but has
no corresponding clear; Option A is the safe default since no queries currently depend
on "exactly one `was_best` per strategy" semantics.

## Acceptance Criteria

- [x] Pick one option and implement. (Option A chosen — permanent audit trail)
- [x] Migration query run against live graph, old property absent from schema.
  `MATCH (r:Run) WHERE r.was_best IS NOT NULL SET r.peaked_as_best = r.was_best REMOVE r.was_best`
  — Completed in 1 ms, 0 records changed (no `was_best` nodes existed in live graph).
- [x] Document chosen semantics in `graph_v1_contract.md` Run node spec.

## Scope
- `qws_graph/research/graph/store.py` — promotion write logic
- `qws_graph/docs/graph_v1_contract.md` — Run node spec update
- Migration query (one-shot, documented in story, not automated)
