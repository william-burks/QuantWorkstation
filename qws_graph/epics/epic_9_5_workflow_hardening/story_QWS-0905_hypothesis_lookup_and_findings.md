# Story 1 — Hypothesis lookup presets + `findings` field

## ID
QWS-0905

## Status
TESTING

## Type
schema

## Blocked On
None

## Summary
Add `findings` text property to `Hypothesis` node and two query presets so researcher can surface hypotheses by status or title fragment without memorizing 12-char IDs.

## Problem
No `qw query --name` preset for hypothesis lookup. No `findings` field to capture session context when parking a hypothesis. After session ends, parked hypothesis loses all reasoning.

## Goal
Researcher can run `qw query --name hypotheses_by_status` to see all hypotheses grouped by status, and `qw query --name hypothesis_search --param title_fragment=<text>` to find by title. `qw record --hypothesis <id> --findings "<text>"` persists session notes on the node.

## Schema Extension
| Element | Type | Properties | Notes |
|---|---|---|---|
| `Hypothesis` | Node | `findings: string` | additive, nullable |

All additions must be registered in `qws_graph/docs/data_dictionary.yaml`.

## In Scope
- `findings` nullable text property on `Hypothesis` node
- `--findings "<text>"` flag on `qw record --hypothesis <id>` — updates `findings` on existing node, does not create new node
- Preset `hypotheses_by_status`: lists all hypotheses grouped by status (`open`, `confirmed`, `rejected`); columns: `hypothesis_id`, `title`, `findings` (truncated 80 chars), `created_at`
- Preset `hypothesis_search`: accepts `title_fragment` parameter; returns matching hypotheses with `hypothesis_id`, `title`, `status`, `findings`
- `data_dictionary.yaml` updated with `findings` property
- `PROVENANCE_ENGINE.md` Hypothesis Key Properties table updated with `findings` entry
- Tests for both presets and `--findings` flag

## Out of Scope
- No changes to other node types
- No changes to existing `hypotheses` preset (if one exists)
- No full-text index setup (CONTAINS clause acceptable for search)

## Repo Touchpoints
<!-- MAX 5 FILES. If you need more, split the story. -->
- `qws_graph/docs/data_dictionary.yaml` — add `findings` to Hypothesis entry
- `qws_graph/research/graph/store.py` — `update_hypothesis_findings()` method
- `qws_graph/research/graph/cli.py` — `--findings` flag on `record --hypothesis`
- `qws_graph/research/graph/query_presets.py` + `query.py` — register + implement `hypotheses_by_status`, `hypothesis_search`
- `docs/PROVENANCE_ENGINE.md` — add `findings` to Hypothesis Key Properties table
- `qws_graph/tests/unit/test_hypothesis_presets.py` — new

## Acceptance Criteria
- [x] `qw record --hypothesis <id> --findings "text"` writes `findings` property; re-run updates value
- [x] `qw query --name hypotheses_by_status` returns all hypotheses sorted by status; `findings` truncated at 80 chars
- [x] `qw query --name hypothesis_search --param title_fragment=sweep` returns hypotheses with "sweep" in title
- [x] `data_dictionary.yaml` has `findings` entry under `Hypothesis`
- [x] `PROVENANCE_ENGINE.md` Hypothesis Key Properties table includes `findings`
- [x] `--findings` on unknown `hypothesis_id` returns error, exits non-zero

## Definition of Done
- [x] data_dictionary.yaml updated
- [x] Tests green
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: `--findings` writes and updates
- type: cli
- cmd: `qw record --hypothesis demo_hyp_001 --findings "Test findings text"`
- expect_contains: "OK: Hypothesis 'demo_hyp_001' findings updated"
- expect_exit: 0

### AC2: `hypotheses_by_status` returns findings truncated at 80 chars
- type: cli
- cmd: `qw query --name hypotheses_by_status`
- expect_contains: "demo_hyp_001"
- expect_exit: 0

### AC3: `hypothesis_search` returns match on title fragment
- type: cli
- cmd: `qw query --name hypothesis_search --param title_fragment=bear`
- expect_contains: "demo_hyp_001"
- expect_exit: 0

### AC4: data_dictionary.yaml has findings entry
- type: file_check
- cmd: `grep -A3 'findings:' qws_graph/docs/data_dictionary.yaml`
- expect_contains: "nullable: true"
- expect_exit: 0

### AC5: PROVENANCE_ENGINE.md has findings in table
- type: file_check
- cmd: `grep 'findings' docs/PROVENANCE_ENGINE.md`
- expect_contains: "findings"
- expect_exit: 0

### AC6: unknown hypothesis_id returns error + exit 1
- type: cli
- cmd: `qw record --hypothesis 000000000000 --findings "text"`
- expect_contains: "not found"
- expect_exit: 1
