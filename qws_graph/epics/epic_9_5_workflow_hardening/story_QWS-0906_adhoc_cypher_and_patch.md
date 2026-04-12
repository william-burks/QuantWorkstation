# Story 2 — Ad-hoc Cypher passthrough + `qw patch`

## ID
QWS-0906

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add `qw query --cypher` for read-only ad-hoc Cypher and `qw patch` for surgical property correction on Run nodes, eliminating throwaway util/ scripts.

## Problem
`qw query` requires a named preset — no way to run one-off read queries during investigation. No `qw patch` command to correct a bad property on an existing Run node; workaround is throwaway util/ scripts that bypass CLI and leave no audit trail.

## Goal
Researcher runs `qw query --cypher "MATCH (s:Strategy) RETURN s LIMIT 10"` for ad-hoc reads. Runs `qw patch --run <run_id> --set sharpe=2.1` to correct a property. Both guarded against accidental writes or out-of-scope property changes.

## Design
- Cypher guard: parse first keyword after stripping whitespace/comments; block if in `{CREATE, MERGE, SET, DELETE, REMOVE, DROP, CALL, LOAD}`. Case-insensitive check.
- `qw patch` whitelist: `profit_factor`, `sharpe`, `win_rate`, `total_trades`, `max_drawdown_r`. Reject writes to `run_id`, `strategy_id`, `created_at`. Type-coerce value from string: float if parseable, else string.
- Dry-run flag on `qw patch`: print Cypher that would execute, no DB write.
- Output format for `--cypher`: JSON lines (one record per line).

## In Scope
- `qw query --cypher "<query>"` in `cli.py`; write-keyword guard; JSON-lines output
- `qw patch --run <run_id> --set <key>=<value>` in `cli.py`; key whitelist; `--dry-run` flag
- Tests: guard rejects SET/MERGE/CREATE; `qw patch` updates correct node; disallowed key returns error; dry-run prints Cypher without writing

## Out of Scope
- No `--cypher` on other node types (Run only for patch)
- No pagination for `--cypher` results
- No `qw patch` for non-Run nodes

## Repo Touchpoints
<!-- MAX 5 FILES. If you need more, split the story. -->
- `qws_graph/research/graph/cli.py` — `query --cypher` subcommand, `patch` command
- `qws_graph/research/graph/store.py` — `run_adhoc_cypher()`, `patch_run()` methods
- `qws_graph/tests/unit/test_adhoc_cypher.py` — new
- `qws_graph/tests/unit/test_patch_run.py` — new

## Acceptance Criteria
- [ ] `qw query --cypher "MATCH (r:Run) RETURN r.run_id LIMIT 5"` returns JSON lines
- [ ] `qw query --cypher "SET r.sharpe = 1"` exits non-zero with "write operation not permitted" message
- [ ] `qw query --cypher "MERGE (x:X)"` exits non-zero
- [ ] `qw patch --run <id> --set sharpe=2.5` updates `sharpe` on correct Run node
- [ ] `qw patch --run <id> --set run_id=bad` exits non-zero with "key not patchable" message
- [ ] `qw patch --run <id> --set sharpe=2.5 --dry-run` prints Cypher, makes no DB change
- [ ] `qw patch --run nonexistent --set sharpe=1.0` exits non-zero with "run not found"

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED
