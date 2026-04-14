# Story 2 — Research Navigator Agent

## ID
QWS-1302

## Status
READY

## Type
code

## Blocked On
QWS-1301 (queued_hypotheses query), ~~QWS-0905~~ (findings field on Hypothesis + hypothesis search presets)

## Summary
Build `research-navigator` agent that synthesizes "what to try next" at session start, gates hypothesis commit with redundancy check, pivots mid-session based on live trial output, and wraps session with updated findings.

## Problem
Current `/research-session` command is a self-serve protocol. Researcher manually runs 4 screening queries, synthesizes what to try next from raw tables, and remembers what was discovered in prior sessions. `list_aborted` returns nothing useful (GAP-007 structural gap). Pre-screening runs inconsistently. No "what next" synthesis — just table dumps.

## Goal
After this story, a `research-navigator` agent:
1. At session start: runs all screening queries + `queued_hypotheses`, reads `findings` from top-3 parked hypotheses, produces a ranked 2-3 next-direction shortlist (not just tables)
2. Before hypothesis commit: silently runs redundancy check, surfaces any matches
3. Mid-session pivot (Phase 3): reads latest trial run output CSV, synthesizes whether to branch, abandon, or continue; surfaces remaining queued alternatives
4. At session end: updates `findings` on parked hypotheses, writes session notes structure, suggests next session starting point

## Design
- Agent file at `.claude/agents/research-navigator.md`
- Model: Opus (synthesis-heavy, not mechanical)
- 4 explicit phases: Start / Direction-chosen / Mid-session-pivot / Session-wrap
- Phase 1 output format: numbered shortlist (1. best direction, 2. second, 3. third) with one-line rationale each — not raw query output
- Phase 3 trigger: researcher pastes trial result path or metrics; navigator reads bundle.json, compares against hypothesis target, recommends branch/abandon/continue
- Guard: `.claude/scripts/agent-research-guard.sh`

## In Scope
- `.claude/agents/research-navigator.md` — update existing agent file: add 4 phases, tool list, output format contracts
- `.claude/scripts/agent-research-guard.sh` — blocks listed below
- Integration test: navigator Phase 1 against current graph produces session brief with ≥ 1 next-direction recommendation

## Out of Scope
- Navigator running trial scripts (that is QWS-1303)
- Navigator writing to `research/trials/` or `research/results/`
- Navigator making graph lifecycle changes (degrade, retire, monitor)
- Auto-selecting direction without researcher approval

## Repo Touchpoints
- `.claude/agents/research-navigator.md` — update existing file
- `.claude/scripts/agent-research-guard.sh` — existing file (already at this path)

## Acceptance Criteria
- [x] `.claude/agents/research-navigator.md` updated with all 4 phases documented
- [x] Phase 1 output is ranked 2-3 direction shortlist with rationale — not raw table output
- [x] Phase 2 redundancy check runs silently before hypothesis commit and surfaces matches if found
- [x] Phase 3 reads bundle.json from provided path and produces branch/abandon/continue recommendation
- [x] Phase 4 updates `findings` on active hypothesis and writes session wrap structure
- [x] Agent reads project memory at session start (`.claude/agent-memory/` relevant files)
- [x] `agent-research-guard.sh` blocks: `qw degrade`, `qw retire`, `qw monitor`, `qw abort`, `qw record --bundle`, git operations, writes outside `research/ideas/`
- [x] Integration test: Phase 1 run against current graph produces structured output. If ≥ 1 Champion or queued Hypothesis exists, output contains ≥ 1 ranked direction with node ID citation. If graph is empty, output states 'No prior research — cold start' with no error.
- [x] Tool list in agent file: Read, Glob, Grep, Bash (scoped to `qw query` and `qw record --hypothesis` only), Write (scoped to `research/ideas/` only)

## Definition of Done
- [x] All ACs passing
- [x] Tests green (where applicable)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: agent file has all 4 phases
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_has_four_phases -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC2: Phase 1 output ranked shortlist format
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_phase1_ranked_shortlist_format -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC3: Phase 2 redundancy check silent
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_phase2_redundancy_check -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: Phase 3 bundle.json pivot
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_phase3_bundle_json -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: Phase 4 findings update
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_phase4_findings_update -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC6: reads project memory
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_reads_project_memory -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC7: guard blocks prohibited commands
- type: cli
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestResearchGuardBlocks -v`
- expect_contains: "7 passed"
- expect_exit: 0

### AC8: integration test — cold start and structured output
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_phase1_cold_start_clause -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC9: tool list scoped
- type: file_check
- cmd: `pytest qws_graph/tests/integration/test_research_navigator.py::TestNavigatorAgentFile::test_tool_list_scoped -v`
- expect_contains: "PASSED"
- expect_exit: 0
