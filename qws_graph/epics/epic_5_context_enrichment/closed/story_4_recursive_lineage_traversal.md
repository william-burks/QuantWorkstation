# Story 4 — Recursive Lineage Traversal

## ID
QWS-0504

## Status
CLOSED

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
# Default (depth=1, Champions only — unchanged behaviour)
qw query --name downstream_champions --param run_id=abc123

# Multi-hop, Champions only
qw query --name downstream_champions --param run_id=abc123 --param depth=5

# Multi-hop, include RetiredChampion nodes
qw query --name downstream_champions --param run_id=abc123 --param depth=5 --param include_retired=true

# Strategy lineage with depth
qw query --name strategy_lineage --param strategy_id=cl-1h-bear-liquidity-sweep --param depth=3
```

## In Scope
- `depth` parameter on `get_downstream_champions_v1(session, run_id, depth=1)`.
- `include_retired` parameter on `get_downstream_champions_v1(session, run_id, depth=1, include_retired=False)`.
  When `True`, `:RetiredChampion` nodes are included in results with a `node_type` field
  (`"champion"` or `"retired_champion"`). When `False` (default), only `:Champion` nodes returned.
- Variable-length Cypher path `[:PIVOTED_FROM*1..$depth]` on both functions.
- `depth` and `include_retired` params added to `downstream_champions` preset in `PRESET_CATALOG`.
- `depth` parameter on `get_strategy_lineage_v1(session, strategy_id, depth=1)`.
- Validation: `depth` must be an integer in `1..10`; error returned otherwise. Same rule applies to both functions.
- Tests covering `depth=1` (unchanged), `depth=3` (multi-hop), `depth=11` (rejected),
  `include_retired=True` (RetiredChampion nodes present + `node_type` field), `include_retired=False` (Champions only).

## Out of Scope
- Recursive traversal on `HAS_RUN` or `USES_CONFIG` edges.
- Auto-detection of maximum depth from graph topology.
- UI visualisation of the ancestry chain.
- Changes to `get_recent_champions_v1` or `get_cross_artifact_correlation_v1`.

## Repo Touchpoints
- `qws_graph/research/graph/query.py` — `GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER`, `get_downstream_champions_v1`, `get_strategy_lineage_v1`
- `qws_graph/research/graph/query_presets.py` — `downstream_champions` preset params (`depth`, `include_retired`)
- `qws_graph/research/graph/cli.py` — no change needed (params come through `--param`)
- `qws_graph/tests/unit/test_lineage_queries.py` — extend existing tests

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
- [x] `qw query --name downstream_champions --param run_id=<id> --param depth=1` returns
  the same results as the current implementation (regression-safe).
- [x] `qw query --name downstream_champions --param run_id=<id> --param depth=3` returns
  champions reachable within 3 `PIVOTED_FROM` hops.
- [x] `depth=11` returns a deterministic `INVALID_PARAMS` error; no graph query executed.
- [x] Default `depth=1` is preserved when the parameter is omitted.
- [x] `include_retired=false` (default) returns only `:Champion` nodes; no `node_type` field required.
- [x] `include_retired=true` returns `:Champion` and `:RetiredChampion` nodes; every row
  includes a `node_type` field (`"champion"` or `"retired_champion"`).
- [x] `get_strategy_lineage_v1` accepts `depth` param (default 1, max 10); same validation as `downstream_champions`.
- [x] `qw query --name strategy_lineage --param strategy_id=<id> --param depth=3` traverses
  multi-generation champion ancestry for the strategy.
- [x] Cypher uses variable-length path `[:PIVOTED_FROM*1..$depth]`; no unbounded `[*]`.
- [x] Docstrings document depth bound, hard cap, and `include_retired` semantics.

## Validation
- Unit tests with `FakeSession` responses for `depth=1`, `depth=3`, `depth=10`.
- Unit test confirming `depth=0` and `depth=11` raise `ValueError`.
- Integration check on seeded graph with a known 2-generation champion chain.

## Definition of Done
- [x] `depth` parameter implemented and tested.
- [x] `downstream_champions` preset docs updated (description and param list).
- [x] Existing `test_lineage_queries.py` tests remain green at `depth=1`.
- [x] Story marked CLOSED after test suite passes.

## Dependencies
- Depends on: `spike_lean_neighborhood_optimization.md` V1 patch (max_results safety cap)
  — this must ship first to ensure the base query is bounded before depth expansion.
- Enables: Full multi-generation champion ancestry tracing for research SOP.

## Design Decisions (resolved)

| Question | Decision |
|---|---|
| Does `get_strategy_lineage_v1` gain `depth` in this story? | Yes — included in scope. Complexity is low: same variable-length pattern applied to the lineage traversal. |
| Hard cap value | `depth=10`. Not configurable via env var — hard-coded in validation. |
| Intermediate nodes in results | Add optional `include_retired` param (default `false`). When `false`: only `:Champion` nodes returned (backward compatible). When `true`: `:Champion` and `:RetiredChampion` nodes both returned, each row includes `node_type` field (`"champion"` or `"retired_champion"`). |

## Notes
The existing `test_lineage_queries.py::TestTraversalDepthBounded` tests assert that no
variable-length paths exist in the current Cypher. Those tests will need to be updated
when this story is implemented to verify that the variable-length path is bounded (not absent).
