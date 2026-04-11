# Story 2 — Parameter Stability Analysis

## ID
QWS-0602

## Status
CLOSED

## Summary
A Python analytics tool (`research/experiments/stability.py`) that takes a champion's
`run_id`, finds all grid sweep runs with neighboring parameter values, and reports
whether the champion sits on a "plateau of profit" or an "island of profit."

## Problem
Parameter optimization produces runs with varying sharpe ratios across the parameter
grid. The "best" run by sharpe may be surrounded by failing runs — an island. A slightly
less optimal parameter set surrounded by other passing runs is actually more robust.

Currently there is no way to answer: "Is this champion's parameter set brittle?"

## Architecture
This is a Python analytics tool, not a graph story. The graph provides the data via
existing queries; pandas/numpy does the computation.

```
graph (run metadata + params) → stability.py → stability report
```

## Design

### Input
A `run_id` (champion's run). The tool:
1. Calls `qw query --name run_history --param strategy_id=<sid>` to get all runs for
   the strategy.
2. Reads `params_json` from each run's associated Config node (via `qw query` or direct
   Neo4j read).
3. Computes pairwise parameter distance between the champion config and all other runs.
4. Defines "neighbors" as runs within a configurable distance threshold per parameter.
5. Computes std dev of Sharpe across neighbors.

### Output
```
Parameter Stability Report: run_id=a1b2c3d4e5f6
  Champion sharpe:     2.31
  Neighbors found:     12 runs
  Neighbor sharpe μ:   1.84
  Neighbor sharpe σ:   0.43
  Stability score:     0.81  (1.0 = perfectly stable plateau)
  Assessment:          ROBUST — champion sits on a broad performance plateau

  Nearest failing neighbor: run_id=b2c3d4e5f6a1, sharpe=0.71, distance=0.15
```

### Stability score
`1 - (σ_neighbors / μ_neighbors)` clamped to [0, 1]. Score > 0.7 = robust; < 0.4 = brittle.
Tunable threshold. Document clearly as a heuristic, not a statistical guarantee.

## Deliverable
- `research/experiments/stability.py` — standalone script and importable module
- CLI: `python -m research.experiments.stability --run-id <id> [--threshold 0.2]`
- Unit tests with seeded mock data

## In Scope
- `research/experiments/stability.py`
- `tests/unit/test_stability.py`
- Optional: `qw query` extension for fetching run+config data in one call (if needed)

## Out of Scope
- Graph schema changes
- Multi-dimensional parameter topology visualization
- Automated re-promotion based on stability score

## Repo Touchpoints
- `research/experiments/stability.py` — new
- `tests/unit/test_stability.py` — new

## Acceptance Criteria
- [x] Given a mock grid where champion sharpe=2.31, neighbor sharpe μ=1.84, σ=0.43:
  stability score is between 0.80 and 0.82, and assessment label is ROBUST.
- [x] Given a mock grid where champion sharpe=2.31, neighbor sharpe μ=0.90, σ=1.10:
  stability score is below 0.40, and assessment label is BRITTLE.
- [x] `--run-id <id>` with no grid sweep neighbors returns a clear "insufficient data" message.
- [x] Stability score is documented as a heuristic with explicit assumptions.
- [x] `python -m research.experiments.stability --run-id <id>` runs from repo root.

## Acceptance Test Plan

### AC1: ROBUST plateau case
- type: regression
- cmd: `pytest tests/unit/test_stability.py::TestRobustCase -q`
- expect_contains: "passed"
- expect_exit: 0

### AC2: BRITTLE island case
- type: regression
- cmd: `pytest tests/unit/test_stability.py::TestBrittleCase -q`
- expect_contains: "passed"
- expect_exit: 0

### AC3: Insufficient data message
- type: regression
- cmd: `pytest tests/unit/test_stability.py::TestInsufficientData -q`
- expect_contains: "passed"
- expect_exit: 0

### AC4: Heuristic documentation
- type: regression
- cmd: `pytest tests/unit/test_stability.py::TestHeuristicDocumentation -q`
- expect_contains: "passed"
- expect_exit: 0

### AC5: CLI entry point
- type: cli
- cmd: `python -m research.experiments.stability --run-id fake123`
- expect_contains: "No live graph connection"
- expect_exit: 1

## Definition of Done
- [x] `stability.py` implemented with unit tests.
- [x] Runbook documents usage example.
  Usage: `python -m research.experiments.stability --run-id <run_id> [--threshold 0.2]`
  Import: `from research.experiments.stability import compute_stability, RunRecord`
  Build RunRecord list from qw query output, call compute_stability(champion, all_runs).
- [x] Story marked CLOSED.
