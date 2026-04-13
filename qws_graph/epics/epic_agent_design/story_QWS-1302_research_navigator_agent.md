# Story 2 — Research Navigator Agent

## ID
QWS-1302

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1301 (queued_hypotheses query), QWS-0905 (findings field on Hypothesis), QWS-0906 (hypothesis search presets)

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
- [ ] `.claude/agents/research-navigator.md` updated with all 4 phases documented
- [ ] Phase 1 output is ranked 2-3 direction shortlist with rationale — not raw table output
- [ ] Phase 2 redundancy check runs silently before hypothesis commit and surfaces matches if found
- [ ] Phase 3 reads bundle.json from provided path and produces branch/abandon/continue recommendation
- [ ] Phase 4 updates `findings` on active hypothesis and writes session wrap structure
- [ ] Agent reads project memory at session start (`.claude/agent-memory/` relevant files)
- [ ] `agent-research-guard.sh` blocks: `qw degrade`, `qw retire`, `qw monitor`, `qw record --bundle`, git operations, writes outside `research/ideas/`
- [ ] Integration test: run navigator Phase 1 against current graph; output contains session brief section and ≥ 1 ranked direction
- [ ] Tool list in agent file: Read, Glob, Bash (scoped to `qw query` and `qw record --hypothesis` only), Write (scoped to `research/ideas/` only)

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green (where applicable)
- [ ] Story marked CLOSED
