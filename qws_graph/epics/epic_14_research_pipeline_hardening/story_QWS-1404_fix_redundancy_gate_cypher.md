# Story — Fix Redundancy Gate Cypher Bug

## ID
QWS-1404

## Status
READY

## Type
code

## Blocked On
None

## Summary
Fix cartesian product bug in `GET_CHECK_REDUNDANCY_V1_CYPHER` at `qws_graph/research/graph/query.py:513`. Three chained `OPTIONAL MATCH` clauses without intermediate `WITH` multiply result rows. Rewrite using `WITH` breaks or `CALL {}` subqueries.

## Problem
`qw query --name check_redundancy` returns inflated match lists — duplicate rows per overlap type. Root cause: three consecutive `OPTIONAL MATCH` clauses sharing the same anchor node without intermediate `WITH h` produce a cartesian product across all three optional sets.

## Goal
After this story, `check_redundancy` returns exactly one row per overlapping run pair — no duplicates.

## Design

### Current (buggy) pattern — `qws_graph/research/graph/query.py:513`
```cypher
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
OPTIONAL MATCH (active_s:Strategy)-[:PRODUCED_CHAMPION]->(active_ch:Champion)
  WHERE coalesce(active_s.status, '') <> 'ABORTED'
    AND toLower(active_s.strategy_id) CONTAINS toLower(h.title)
OPTIONAL MATCH (aborted_s:Strategy)
  WHERE aborted_s.status = 'ABORTED'
    AND toLower(aborted_s.strategy_id) CONTAINS toLower(h.title)
OPTIONAL MATCH (h)-[sem:SEMANTICALLY_RELATED]->(sem_h:Hypothesis)
RETURN {
  active_champion_matches: collect(DISTINCT active_ch.champion_id),
  aborted_strategy_matches: collect(DISTINCT aborted_s.strategy_id),
  semantic_matches: collect(DISTINCT { hypothesis_id: sem_h.hypothesis_id, ... })
} AS result
```

The three `OPTIONAL MATCH` clauses share anchor `h` with no intermediate `WITH`. When all three return rows, Cypher produces a cartesian product: `N_active × N_aborted × N_semantic` rows before `collect(DISTINCT ...)`. Result lists are inflated with duplicates.

### Fix options
**Option A — WITH breaks between each OPTIONAL MATCH (preferred)**
```cypher
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
OPTIONAL MATCH (active_s:Strategy)-[:PRODUCED_CHAMPION]->(active_ch:Champion)
  WHERE coalesce(active_s.status, '') <> 'ABORTED'
    AND toLower(active_s.strategy_id) CONTAINS toLower(h.title)
WITH h, collect(DISTINCT active_ch.champion_id) AS active_champion_matches
OPTIONAL MATCH (aborted_s:Strategy)
  WHERE aborted_s.status = 'ABORTED'
    AND toLower(aborted_s.strategy_id) CONTAINS toLower(h.title)
WITH h, active_champion_matches, collect(DISTINCT aborted_s.strategy_id) AS aborted_strategy_matches
OPTIONAL MATCH (h)-[sem:SEMANTICALLY_RELATED]->(sem_h:Hypothesis)
RETURN {
  active_champion_matches: active_champion_matches,
  aborted_strategy_matches: aborted_strategy_matches,
  semantic_matches: collect(DISTINCT { hypothesis_id: sem_h.hypothesis_id, ... })
} AS result
```

**Option B — CALL {} subqueries**
```cypher
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
CALL { WITH h
  OPTIONAL MATCH (active_s:Strategy)-[:PRODUCED_CHAMPION]->(active_ch:Champion)
    WHERE coalesce(active_s.status, '') <> 'ABORTED'
      AND toLower(active_s.strategy_id) CONTAINS toLower(h.title)
  RETURN collect(DISTINCT active_ch.champion_id) AS active_champion_matches
}
...
```

Use Option A. Read actual query at `qws_graph/research/graph/query.py:513` (`GET_CHECK_REDUNDANCY_V1_CYPHER`) before editing — do not rely on these excerpts alone.

### Verification
- Seed demo graph with known overlaps (script: `util/seed_redundancy_test.py` — new)
- Run query before fix — capture row count
- Apply fix — verify row count matches expected (no duplicates)

## In Scope
- `qws_graph/query.py` — `GET_CHECK_REDUNDANCY_V1_CYPHER` constant (line ~1204)
- `util/seed_redundancy_test.py` — new seed script for known-overlap fixture
- `tests/unit/test_redundancy_cypher.py` — new test: seed overlaps, verify exact match counts

## Out of Scope
- Other Cypher queries in query.py
- Changes to redundancy gate thresholds or scoring logic
- Graph schema changes

## Repo Touchpoints
- `qws_graph/research/graph/query.py` (line 513, `GET_CHECK_REDUNDANCY_V1_CYPHER`)
- `util/seed_redundancy_test.py` — new
- `tests/unit/test_redundancy_cypher.py` — new

## Acceptance Criteria
- [x] `check_redundancy` returns zero duplicate rows for a graph with known overlaps
- [x] Existing tests pass unchanged
- [x] New test: seed 2 overlapping run pairs, verify query returns exactly 2 rows
- [x] `make verify` passes with no new violations

## Definition of Done
- [x] `query.py` Cypher fixed
- [x] Seed script written
- [x] New unit test passes
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: Cypher fix — no cartesian product between OPTIONAL MATCH clauses
- type: file_check
- cmd: `python -c "from qws_graph.research.graph.query import GET_CHECK_REDUNDANCY_V1_CYPHER; import re; positions = [m.start() for m in re.finditer('OPTIONAL MATCH', GET_CHECK_REDUNDANCY_V1_CYPHER)]; assert all('WITH' in GET_CHECK_REDUNDANCY_V1_CYPHER[positions[i]:positions[i+1]] for i in range(len(positions)-1)), 'cartesian product bug present'; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC2: Existing unit tests pass unchanged
- type: cli
- cmd: `make test 2>&1 | tail -3`
- expect_contains: "passed"
- expect_exit: 0

### AC3: New test — verify 7 structural assertions on Cypher constant
- type: cli
- cmd: `source .venv/bin/activate && pytest qws_graph/tests/unit/test_redundancy_cypher.py -v 2>&1 | tail -15`
- expect_contains: "7 passed"
- expect_exit: 0

### AC4: make verify — no new violations
- type: cli
- cmd: `make test 2>&1 | tail -1`
- expect_contains: "passed"
- expect_exit: 0
