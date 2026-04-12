# Story 4 — Correlation Gate Re-check

## ID
QWS-0804

## Status
CLOSED

## Blocked On
—

## Summary
Add `qw gate --recheck` CLI command that re-evaluates the correlation gate (`corr < 0.30`) for
all current promotion candidates against the active Champion portfolio — without re-running any
trial. Reads existing `CORRELATED_WITH` edges (QWS-0603). Writes nothing to the graph.

## Problem
The correlation gate is checked once at trial promotion time. When a Champion is promoted or
degraded, the portfolio composition changes. A candidate that previously failed (`corr >= 0.30`
against an existing Champion) may now pass — that Champion no longer exists. There is no way to
re-evaluate this without re-running the full trial. `qw gate --recheck` fills that gap.

## Goal
```zsh
# Re-evaluate correlation gate for all promotion candidates
qw gate --recheck

# Example output
Rechecking correlation gate for 4 candidates against 3 active Champions...

candidate_id          max_corr   gate
--------------------  ---------  ------
strat_abc123          0.18       PASS
strat_def456          0.27       PASS
strat_ghi789          0.34       FAIL
strat_jkl012          0.11       PASS

3 / 4 candidates pass (corr < 0.30)
```

## Schema
No new schema. Reads `CORRELATED_WITH` edges written by QWS-0603. Writes nothing.

## In Scope
- `qw gate --recheck` subcommand
- Read `CORRELATED_WITH` edges from graph; identify active Champions as portfolio
- Compute max correlation per candidate against current active Champions only
- Output: pass/fail per candidate with current max correlation value
- Exit code 0 if all pass; exit code 1 if any fail (for scripted use)

## Out of Scope
- `--update` flag to mark passing candidates as promotion-eligible (keeps story small)
- `--strategy-id` scoping (v1 always re-checks all candidates)
- Writing any nodes, edges, or properties to the graph
- Auto-promotion on pass

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — add `gate` command with `--recheck` flag
- `qws_graph/research/graph/store.py` — read `CORRELATED_WITH` edges, compute max corr per candidate against active Champions
- `qws_graph/research/graph/query_presets.py` — helper to fetch current promotion candidates
- `qws_graph/tests/unit/test_gate_recheck.py` — new

## Acceptance Criteria
- [x] `qw gate --recheck` runs without error when graph has no `CORRELATED_WITH` edges (empty output, not exception)
- [x] Output table shows `candidate_id`, `max_corr`, and `gate` (PASS/FAIL) for each candidate
- [x] Gate threshold is `corr < 0.30` (consistent with QWS-0603)
- [x] Only active Champions (not FormerChampion, RetiredChampion) contribute to the portfolio set
- [x] Exit code is `0` if all candidates pass; `1` if any fail
- [x] No writes to the graph in any code path

## Definition of Done
- [x] `qw gate --recheck` command implemented and tested
- [x] Unit tests cover: all-pass, partial-fail, empty portfolio, empty candidate set
- [x] `ruff check .` and `mypy --strict .` clean (pre-existing mypy error in qws_graph/data/__init__.py unrelated to this story)
- [x] All affected README files updated (no new nodes/edges — no README changes required)
- [x] PROVENANCE_ENGINE.md updated if new nodes/edges/properties introduced (no schema changes)

## Acceptance Test Plan

### AC1: Empty edge set — no exception
- type: cli
- cmd: `qw gate --recheck`
- expect_contains: "No promotion candidates found."
- expect_exit: 0

### AC2: Output table columns present
- type: cli
- cmd: `qw gate --recheck`
- expect_contains: "candidate_id"
- expect_exit: 0

### AC3: Gate threshold corr < 0.30
- type: file_check
- cmd: grep for `"PASS" if max_corr < corr_threshold` in `qws_graph/research/graph/store.py`
- expect_contains: PASS if max_corr < corr_threshold

### AC4: Only active Champions in portfolio set
- type: file_check
- cmd: grep for `FormerChampion` in `_RECHECK_CYPHER` in `qws_graph/research/graph/store.py`
- expect_contains: NOT ac:FormerChampion AND NOT ac:RetiredChampion

### AC5: Exit code 0 all-pass, 1 any-fail
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_gate_recheck.py::TestCmdGate::test_all_pass_exit_0 qws_graph/tests/unit/test_gate_recheck.py::TestCmdGate::test_any_fail_exit_1 -v`
- expect_contains: 2 passed

### AC6: No writes
- type: file_check
- cmd: grep for `execute_write` in `get_correlation_gate_recheck_v1` in `store.py`
- expect_contains: (no match — only execute_read)
