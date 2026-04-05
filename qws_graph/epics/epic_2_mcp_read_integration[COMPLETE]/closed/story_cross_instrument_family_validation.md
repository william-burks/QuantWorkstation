# Story — Cross-Instrument Family Validation

## Status
CLOSED

## Priority
P2 — Research Integrity. `get_cross_artifact_correlation_v1` currently requires a
`strategy_id` anchor. Once baselines and sweep strategies share a `family_id`, the more
natural query is "show me all members of this family" without needing to nominate a specific
anchor strategy first. The `family_id` path is also what MCP tool callers prefer.

## Problem
The `cross_artifact_correlation` preset has `strategy_id` as required. This blocks two
real workflows:

1. **Direct family inspection.** You have `family_id = 7305f90925f6` and want to see all
   instruments in that family. You should not have to pick an anchor strategy first.

2. **MCP / AI agent access.** An agent building a context neighborhood has the `family_id`
   from a prior query. Forcing it to resolve a `strategy_id` first adds a round-trip and
   introduces a redundant anchor-selection step.

## Goal
Make `strategy_id` and `family_id` both accepted as optional parameters on the
`cross_artifact_correlation` preset. At least one must be provided. `family_id` is the
preferred path when both are available.

## Two Modes

### Mode A — Strategy anchor (existing behaviour, `strategy_id` provided)
Resolves the anchor's `family_id` from the graph and returns all other strategies in the
same family. Falls back to `logic_type + direction` when `family_id IS NULL`.
Behaviour unchanged from current implementation.

### Mode B — Direct family scan (`family_id` provided)
No anchor strategy required. Returns ALL strategies with `strategy.family_id = $family_id`,
including every instrument and timeframe variant. The `anchor_strategy_id` field in the
output is set to the `family_id` string (e.g. `"7305f90925f6"`) to make the query axis
explicit to callers.

**Why separate Cypher, not OR-branch:** An OR anchor
(`WHERE anchor.strategy_id = $strategy_id OR anchor.family_id = $family_id`) expands
multiple anchors for Mode B — every family member becomes an anchor, generating N×(N-1)
result pairs with duplicates. A dedicated `MATCH (s:Strategy {family_id: $family_id})`
scan returns N flat rows cleanly.

## Required Changes

### `research/graph/query.py`
1. Add `GET_FAMILY_CLUSTER_V1_CYPHER` — scans by `family_id`, returns same row shape as
   `GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER` with `anchor_strategy_id = $family_id`.
2. Update `get_cross_artifact_correlation_v1(session, strategy_id=None, family_id=None)` —
   routes to Mode A or Mode B Cypher. Raises `ValueError` when neither is provided.
3. Update `GraphQueryService.get_cross_artifact_correlation_v1()` to accept both params.

### `research/graph/query_presets.py`
1. Move `strategy_id` from `required=True` to `required=False`.
2. Add `family_id` as `required=False` (preferred).
3. Update `validate_params` **or** `run_preset` to raise a clear error when neither is supplied.
4. Pass `family_id` to `service.get_cross_artifact_correlation_v1()` when provided.

## Acceptance Criteria
- [x] `qw query --name cross_artifact_correlation --param strategy_id=<anchor_strategy_id>`
      returns family peers (Mode A).
- [x] `qw query --name cross_artifact_correlation --param family_id=<family_id>` returns all
      family members without a strategy anchor (Mode B).
- [x] Providing neither `strategy_id` nor `family_id` exits `1` with a clear error message.
- [x] Providing both is accepted — `family_id` takes precedence (Mode B used).
- [x] Unit tests cover: Mode A, Mode B, neither-error, both-prefers-family_id.

## Out of Scope
- Changes to Mode A Cypher behaviour.
- Adding `family_id` as a first-class CLI flag (not needed — `--param family_id=<hash>` works).
- `CrossArtifactRowV1` shape changes (reusing `anchor_strategy_id` for the family hash is sufficient).

## Definition of Done
- [x] Both modes work end-to-end via `qw query`.
- [x] Unit tests passing.
- [x] Story marked CLOSED.

## Implementation Notes (2026-04-04)

- `research/graph/query.py` includes `GET_FAMILY_CLUSTER_V1_CYPHER` and dual-mode routing in
  `get_cross_artifact_correlation_v1(session, strategy_id=None, family_id=None)`.
- `family_id` path takes precedence when both parameters are provided.
- Missing parameter pair is validated with a clear error from preset routing:
  `cross_artifact_correlation requires family_id (preferred) or strategy_id`.
- Unit coverage validated:
  - `python -m pytest tests/unit/test_lineage_queries.py -q` (40 passed)
  - `python -m pytest tests/unit/test_qw_query.py -q` (48 passed)
- End-to-end `qw query` checks validated against local Neo4j by creating/removing temporary
  `Strategy` nodes sharing `family_id=story4fam1234`:
  - Mode A (`--param strategy_id=story4-modea-anchor`) returned peer rows.
  - Mode B (`--param family_id=story4fam1234`) returned all family members with
    `anchor_strategy_id` set to the family hash.
  - Neither parameter returned exit code `1` with clear error message.
  - Both parameters used Mode B precedence.

## Dependencies
- Depends on: Churn Story 1 — CLOSED (`family_id` on `Strategy` nodes).
- Depends on: Story 2 (`qw query` preset infrastructure) — CLOSED.
