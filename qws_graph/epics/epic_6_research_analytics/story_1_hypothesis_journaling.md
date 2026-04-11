# Story 1 — Hypothesis & Research Journaling

## ID
QWS-0601

## Status
TESTING

## Summary
Introduce `:Hypothesis` nodes that link qualitative research hypotheses to strategies,
runs, and other graph nodes. Turns the graph into a research journal where "why I ran
this" is permanently connected to "what the results showed." Directly addresses context
drift.

## Problem
Research context lives in the researcher's head, in Slack messages, or in scattered
markdown notes. Six months after a test run:
- Why was this parameter sweep done? Unknown.
- Which hypothesis did this golden run confirm or refute? Unknown.
- Are runs A, B, and C part of the same research thread? Unknown.

`curator_note` on Run nodes helps for single-run annotations but cannot link a
hypothesis to multiple runs or track whether the hypothesis was confirmed.

## Goal
```zsh
# Record a new hypothesis (user-initiated)
qw record --hypothesis "Tuesday London Open has a specific liquidity trap in CL bear"
# → creates Hypothesis node, prints hypothesis_id
# → creates SUGGESTED edge with source="user"

# Link hypothesis to a strategy when a trial is run
qw record --hypothesis <hypothesis_id> --tested-as <strategy_id>

# Link hypothesis to a prior node when pivoting (context bridge)
qw record --hypothesis <hypothesis_id> --branched-from <node_id> --rationale "<text>"

# Update status
qw record --hypothesis <id> --status confirmed|refuted|abandoned|open

# Query
qw query --name list_hypotheses
qw query --name hypothesis_audit --param hypothesis_id=<id>
qw query --name check_redundancy --param hypothesis_id=<id>
```

## Schema

### `:Hypothesis` node
```
hypothesis_id: str          # hash12(title, created_at_iso)
title: str                  # short description (≤ 200 chars)
status: str                 # open | confirmed | refuted | abandoned
created_at: datetime
updated_at: datetime
```

### `SUGGESTED` edge: `(LLM/User)-[:SUGGESTED {source: str}]->(Hypothesis)`
```
source: str                 # "user" for CLI-created; "llm" for AI-initiated
```
Created at hypothesis creation time. For `qw record --hypothesis "<title>"`, source is "user".

### `TESTED_AS` edge: `(Hypothesis)-[:TESTED_AS]->(Strategy)`
Links a hypothesis to a strategy when a trial is run. Created via
`qw record --hypothesis <id> --tested-as <strategy_id>`.

### `BRANCHED_FROM` edge: `(Hypothesis)-[:BRANCHED_FROM {rationale: str}]->(any_node)`
```
rationale: str              # why this hypothesis branched from the source node
```
Context bridge for research pivots. Created via
`qw record --hypothesis <id> --branched-from <node_id> --rationale "<text>"`.

## CLI surface
- `qw record --hypothesis "<title>"` — creates Hypothesis node, prints `hypothesis_id`,
  creates SUGGESTED edge with `source="user"`.
- `qw record --hypothesis <id> --tested-as <strategy_id>` — creates TESTED_AS edge
  linking hypothesis to strategy.
- `qw record --hypothesis <id> --branched-from <node_id> --rationale "<text>"` — creates
  BRANCHED_FROM edge with rationale property.
- `qw record --hypothesis <id> --status confirmed|refuted|abandoned|open` — updates
  `status` on the node.

## MCP tools / Query presets
- `list_hypotheses` — all Hypothesis nodes ordered by `created_at` DESC. Columns:
  `hypothesis_id`, `title`, `status`, `created_at`.
- `log_hypothesis` — creates a Hypothesis node via MCP (for AI-initiated hypotheses);
  equivalent to CLI create; creates SUGGESTED edge with `source="llm"`.
- `check_redundancy --param hypothesis_id=<id>` — given a hypothesis_id, checks:
  active Champions for similar strategy logic (string match on title), `list_aborted`
  for aborted strategies. Returns: match found / no match. (FormerChampion
  cause-of-death check deferred to QWS-0801.)
- `hypothesis_audit --param hypothesis_id=<id>` — traces current state back: what
  TESTED_AS strategies exist, what runs and outcomes are downstream, what Champions
  exist downstream.

## In Scope
- `:Hypothesis` node in `store.py`
- `SUGGESTED`, `TESTED_AS`, `BRANCHED_FROM` edges in `store.py`
- Four CLI modes on `qw record`: `--hypothesis "<title>"`, `--tested-as`, `--branched-from`, `--status`
- `list_hypotheses`, `log_hypothesis`, `check_redundancy`, `hypothesis_audit` query presets
- `data_dictionary.yaml` and `graph_v1_contract.md` updated for node and all new edges
- Unit tests for store methods and CLI parsing

## Out of Scope
- AI-generated hypothesis title suggestions (LLM surface only — journaling is manual)
- Linking hypotheses to Run nodes directly (use Strategy via TESTED_AS instead)

## Repo Touchpoints
- `qws_graph/research/graph/store.py`
- `qws_graph/research/graph/cli.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_hypothesis_journaling.py` — new

## Acceptance Criteria
- [x] `qw record --hypothesis "Test title"` creates a Hypothesis node, prints its ID,
  and creates a SUGGESTED edge with `source="user"`.
- [x] `qw record --hypothesis <id> --tested-as <strategy_id>` creates a TESTED_AS edge
  linking hypothesis to strategy.
- [x] `qw record --hypothesis <id> --branched-from <node_id> --rationale "reason"`
  creates a BRANCHED_FROM edge with `rationale` property set.
- [x] `qw query --name list_hypotheses` returns all hypotheses.
- [x] `qw query --name hypothesis_audit --param hypothesis_id=<id>` returns full
  downstream state: linked strategies, runs, outcomes.
- [x] `qw query --name check_redundancy --param hypothesis_id=<id>` returns match
  results for existing champions and aborted strategies.
- [x] `qw record --hypothesis <id> --status confirmed` updates `status` on the node.
- [x] Supplying a non-existent `strategy_id` to `--tested-as` returns a clear error.
- [x] `log_hypothesis` MCP preset creates a Hypothesis node with `source="llm"` on the
  SUGGESTED edge.

## Acceptance Test Plan

### AC1: qw record --hypothesis "<title>" creates Hypothesis node
- type: cli
- cmd: `python -m research.graph.cli record --hypothesis "Tuesday London Open CL bear liquidity trap"`
- expect_contains: "OK: Hypothesis created"
- expect_exit: 0

### AC2: qw record --hypothesis <id> --tested-as <strategy_id>
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestStoreLinkHypothesisTestedAs -v`
- expect_contains: "passed"
- expect_exit: 0

### AC3: qw record --hypothesis <id> --branched-from <node_id> --rationale "reason"
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestStoreLinkHypothesisBranchedFrom -v`
- expect_contains: "passed"
- expect_exit: 0

### AC4: qw query --name list_hypotheses
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestHypothesisPresetRouting::test_list_hypotheses_routing -v`
- expect_contains: "passed"
- expect_exit: 0

### AC5: qw query --name hypothesis_audit --param hypothesis_id=<id>
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestHypothesisPresetRouting::test_hypothesis_audit_routing -v`
- expect_contains: "passed"
- expect_exit: 0

### AC6: qw query --name check_redundancy --param hypothesis_id=<id>
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestHypothesisPresetRouting::test_check_redundancy_routing -v`
- expect_contains: "passed"
- expect_exit: 0

### AC7: qw record --hypothesis <id> --status confirmed
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestStoreUpdateHypothesisStatus -v`
- expect_contains: "passed"
- expect_exit: 0

### AC8: non-existent strategy_id returns clear error
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestHypothesisCLI::test_tested_as_strategy_not_found -v`
- expect_contains: "passed"
- expect_exit: 0

### AC9: log_hypothesis MCP creates with source="llm"
- type: regression
- cmd: `python -m pytest qws_graph/tests/unit/test_hypothesis_journaling.py::TestMcpLogHypothesis -v`
- expect_contains: "passed"
- expect_exit: 0

## Definition of Done
- [x] Node type, edges, CLI modes, query presets implemented and tested.
- [x] Docs updated (`data_dictionary.yaml`, `graph_v1_contract.md`).
- [ ] Story marked CLOSED.
