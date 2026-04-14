> **SUPERSEDED** — Active canonical story: `qws_graph/epics/epic_agent_design/story_QWS-1302_research_navigator_agent.md`
> Do NOT implement from this file — agents searching by name will find the canonical story first.

# Story 2 — Research Navigator Agent

## ID
QWS-1302

## Status
DRAFT

## Blocked On
Epic 7 COMPLETE (QWS-0801, QWS-0703, QWS-0704 all CLOSED on main)

## Summary
Create `.claude/agents/research-navigator.md` — an Opus-model agent that loads graph state,
surfaces promotion candidates, scans unprocessed ideas, and proposes research direction.
Create `.claude/scripts/agent-research-guard.sh` to block trial execution, ingest, and
champion lifecycle commands. Register guard hook in agent definition.

## Problem
Ideation currently happens in sessions with no graph access. The navigator role exists in
docs but has no agent definition — so each research session requires manual context loading,
manual graph queries, and manual redundancy checks. Without a dedicated agent, Will bridges
context gaps by hand every session.

## Goal

```zsh
# Will spawns navigator in a research session
# Navigator runs:
#   qw query --name recent_champions
#   qw query --name former_champions
#   qw query --name list_aborted
#   qw query --name promotion_candidates
#   lists research/ideas/*.md (status: raw)
# Produces structured Session Brief
# Asks Will for direction
# If novel → logs hypothesis + redundancy check → hands off to trial-engineer if approved
# If "review" → surfaces patterns, no new trials
```

## Agent Definition

**Model:** `claude-opus-4-5` (or latest Opus)
**Tools:** `Bash`, `Read`, `Grep`, `Glob`, `Write` (Write restricted to `research/ideas/` only by guard)
**Memory:** project
**Effort:** high
**Skills:** [caveman]

### Hard Rules (in agent definition body)
- MUST run `qw query --name recent_champions` before any strategy suggestion
- MUST run `qw query --name former_champions` before any strategy suggestion
- MUST run `qw query --name list_aborted` before any strategy suggestion
- MUST run `qw check_redundancy` before logging any hypothesis
- CANNOT run backtests — no `python research/` or `python -m research`
- CANNOT ingest results — no `qw record --bundle`
- CANNOT run `qw abort`, `qw degrade`, `qw retire`
- CANNOT commit or push
- CANNOT promote or demote champions
- `BRANCHED_FROM` rationale is non-optional on any pivot — if navigator proposes a pivot,
  it MUST state the source node and rationale before Will approves

### Guard Script Blocks
`.claude/scripts/agent-research-guard.sh` blocks:
- `python research/` (all research module execution)
- `python -m research` (module invocation)
- `research/bin/` (shell runners)
- `qw record --bundle`
- `qw abort`
- `qw degrade`
- `qw retire`
- `git commit`
- `git push`
- Writes outside `research/ideas/` (enforced by guard on Write tool)

### Hook Registration
PreToolUse Bash and Write matchers → `agent-research-guard.sh`

## In Scope
- `.claude/agents/research-navigator.md` — full agent definition
- `.claude/scripts/agent-research-guard.sh` — guard script following agent-guard.sh pattern

## Out of Scope
- Any graph schema changes
- Any CLI changes
- Research session command rewrite (QWS-0904)
- Trial execution (QWS-0903)

## Repo Touchpoints
- `.claude/agents/research-navigator.md` (new)
- `.claude/scripts/agent-research-guard.sh` (new)

## Acceptance Criteria
- [ ] `.claude/agents/research-navigator.md` exists with correct frontmatter (name, model, tools,
  memory, effort, skills, hooks)
- [ ] Agent body contains all hard rules: mandatory graph queries before suggestion, redundancy
  check before hypothesis log, BRANCHED_FROM non-optional on pivots
- [ ] Agent body explicitly prohibits: `python research/`, `qw record --bundle`, `qw abort`,
  `qw degrade`, `qw retire`, `git commit`, `git push`
- [ ] `.claude/scripts/agent-research-guard.sh` exists, is executable, and blocks all prohibited
  commands (test: echo each blocked pattern through the script, verify exit 2)
- [ ] Guard script follows same stdin JSON pattern as `agent-guard.sh`
- [ ] Hook registered in agent definition under PreToolUse Bash matcher

## Definition of Done
- [ ] `research-navigator.md` agent definition present and correctly formed
- [ ] `agent-research-guard.sh` present, executable, blocks all prohibited patterns
- [ ] Manual smoke test: spawn navigator, verify it runs graph queries before responding
- [ ] All tests pass (`make verify` passes)
- [ ] Story marked CLOSED
