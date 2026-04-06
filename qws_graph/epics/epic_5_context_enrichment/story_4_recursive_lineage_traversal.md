# Story 4 — Recursive Lineage Traversal

## ID
QWS-0504

## Status
draft

## Priority
P3 — Feature Enhancement. The current depth=1 bound is safe and correct for V1. This is a
"nice-to-have" that becomes valuable once the graph has multi-generation champion histories
(i.e., Champion A pivoted from Run B, which led to Champion C, which pivoted from Run D).
Implement after the P1 safety cap (spike) and P2 family definitions are stable.

## Summary
Extend `get_downstream_champions_v1` and `get_strategy_lineage` to support optional unbounded
(or depth-bounded) traversal via a `depth` parameter. Default behaviour remains depth=1 to
preserve V1 performance guarantees.

## Problem
The current `get_downstream_champions_v1(run_id)` traversal is hardcoded to one hop:
```
(Champion)-[:PIVOTED_FROM]->(Run)
```
This is safe but limited. As the graph accumulates multi-generation histories — where a
champion's pivot run itself traces back to an earlier champion — an operator cannot answer
"what is the full ancestry of this champion?" without issuing multiple manual queries.

Similarly, `get_strategy_lineage_v1` shows champions produced by a strategy, but not the
transitive chain of how each champion evolved from prior runs.

## Goal
Add a `depth` parameter (default `1`, max `10`) to the downstream-champion traversal path,
exposed via the `downstream_champions` preset as `--param depth=N`. Document the traversal
semantics and ensure the default is unchanged.

## Inputs
- `research/graph/query.py` — `GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER` and
  `get_downstream_champions_v1`
- `research/graph/query_presets.py` — `downstream_champions` preset
- `research/graph/cli.py` — `qw query` subcommand
- `docs/graph_v1_contract.md` — canonical path `(:Champion)-[:PIVOTED_FROM]->(:Run)`
- `spike_lean_neighborhood_optimization.md` — depth-limit context (Option B)

## Proposed Design

### Cypher Change
Replace the fixed-hop pattern with a variable-length path:
```cypher
-- Current (depth=1)
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)-[:PIVOTED_FROM]->(r:Run {run_id: $run_id})

-- Proposed (variable depth, $depth is an integer parameter)
MATCH path = (ch:Champion)-[:PIVOTED_FROM*1..$depth]->(r:Run {run_id: $run_id})
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch)
```

This returns all champions reachable from `run_id` within `depth` hops of `PIVOTED_FROM`
traversal. At `depth=1` the result is identical to the current implementation.

For `get_strategy_lineage_v1` recursive mode:
```cypher
-- Proposed: full ancestor chain for a champion
MATCH (s:Strategy {strategy_id: $strategy_id})-[:PRODUCED_CHAMPION]->(ch:Champion)
OPTIONAL MATCH chain = (ch)-[:PIVOTED_FROM*1..$depth]->(r:Run)
```

### Parameter Semantics
| `depth` | Traversal | Use case |
|---|---|---|
| `1` (default) | Direct children only | Current V1 behaviour; always safe |
| `2–5` | Grandchildren / 2–3 generations | Tracing champion evolution over a research cycle |
| `6–10` | Deep ancestry | Investigating long-lived strategy families; use with caution |
| `>10` | Rejected | Hard upper bound; returns `INVALID_PARAMS` error |

### CLI Surface
```zsh
# Default (depth=1, unchanged)
qw query --name downstream_champions --param run_id=abc123

# Recursive (depth=5)
qw query --name downstream_champions --param run_id=abc123 --param depth=5

# Full ancestry (depth=10, max)
qw query --name downstream_champions --param run_id=abc123 --param depth=10
```

The `--param recursive=true` shorthand described in earlier notes is not preferred; an explicit
`depth=N` is more precise and avoids boolean flag ambiguity. If `recursive=true` is needed as
an alias, it maps to `depth=10` (the hard maximum).

## In Scope
- `depth` parameter on `get_downstream_champions_v1(session, run_id, depth=1)`.
- Variable-length Cypher path `[:PIVOTED_FROM*1..$depth]`.
- `depth` param added to `downstream_champions` preset in `PRESET_CATALOG`.
- Validation: `depth` must be an integer in `1..10`; error returned otherwise.
- Optional: `depth` param on `get_strategy_lineage_v1` (evaluate during implementation).
- Tests covering `depth=1` (unchanged), `depth=3` (multi-hop), `depth=11` (rejected).

## Out of Scope
- Recursive traversal on `HAS_RUN` or `USES_CONFIG` edges.
- Auto-detection of maximum depth from graph topology.
- UI visualisation of the ancestry chain.
- Changes to `get_recent_champions_v1` or `get_cross_artifact_correlation_v1`.

## Repo Touchpoints
- `research/graph/query.py` — `GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER`, `get_downstream_champions_v1`
- `research/graph/query_presets.py` — `downstream_champions` preset params
- `research/graph/cli.py` — no change needed (depth comes through `--param depth=N`)
- `tests/unit/test_lineage_queries.py` — extend existing tests

## Implementation Notes
- Keep `depth` as a Python `int` parameter, not a string. The preset layer receives
  `--param depth=5` as a string and must cast via `int(params.get("depth", "1"))`.
- Validate `1 <= depth <= 10` in the view function, not the Cypher; raise `ValueError` for
  out-of-range values so the preset layer can map it to `INVALID_PARAMS`.
- Neo4j variable-length paths can be expensive on large graphs — this is why the hard cap
  of 10 is enforced. The `spike_lean_neighborhood_optimization.md` Option A cap should be
  implemented first to ensure the base query is already bounded before depth is added.
- At `depth=1`, the generated Cypher should be equivalent to the current fixed-hop Cypher
  (verify via unit test snapshot).

## Acceptance Criteria
- [ ] `qw query --name downstream_champions --param run_id=<id> --param depth=1` returns
  the same results as the current implementation (regression-safe).
- [ ] `qw query --name downstream_champions --param run_id=<id> --param depth=3` returns
  champions reachable within 3 `PIVOTED_FROM` hops.
- [ ] `depth=11` returns a deterministic `INVALID_PARAMS` error; no graph query executed.
- [ ] Default `depth=1` is preserved when the parameter is omitted.
- [ ] Cypher uses variable-length path `[:PIVOTED_FROM*1..$depth]`; no unbounded `[*]`.
- [ ] Docstring documents the depth bound and the hard cap.

## Validation
- Unit tests with `FakeSession` responses for `depth=1`, `depth=3`, `depth=10`.
- Unit test confirming `depth=0` and `depth=11` raise `ValueError`.
- Integration check on seeded graph with a known 2-generation champion chain.

## Definition of Done
- [ ] `depth` parameter implemented and tested.
- [ ] `downstream_champions` preset docs updated (description and param list).
- [ ] Existing `test_lineage_queries.py` tests remain green at `depth=1`.
- [ ] Story marked CLOSED after test suite passes.

## Dependencies
- Depends on: `spike_lean_neighborhood_optimization.md` V1 patch (max_results safety cap)
  — this must ship first to ensure the base query is bounded before depth expansion.
- Enables: Full multi-generation champion ancestry tracing for research SOP.

## Open Questions
- Should `get_strategy_lineage_v1` also gain a `depth` parameter in this story, or is it
  a separate follow-on? (Scope decision for implementation planning.)
- Is `depth=10` the right hard cap, or should it be configurable via env var?
- Should the recursive results include intermediate `Run` nodes in the path, or only the
  terminal `Champion` nodes at each generation?

## Notes
The existing `test_lineage_queries.py::TestTraversalDepthBounded` tests assert that no
variable-length paths exist in the current Cypher. Those tests will need to be updated
when this story is implemented to verify that the variable-length path is bounded (not absent).
