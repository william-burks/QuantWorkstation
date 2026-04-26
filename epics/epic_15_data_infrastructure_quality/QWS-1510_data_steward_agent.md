# Story — Data Steward Agent

## ID
QWS-1510

## Status
PLANNED

## Type
agent

## Blocked On
QWS-1501, QWS-1504

## Summary
Build the `data-steward` agent that owns data layer health: runs pre-flight health scripts at session start and triages Prefect-raised data errors.

## Problem
Phase A ships `bar_health.py` and `check_feeds.py`, but nobody runs them. research-navigator's scope is `qw query` + graph reads; its guard does not allow python script execution. Without an owner for the data-layer pre-flight, the infrastructure ships and rots. Prefect-raised `SchemaError` / `RollAnomalyError` / CONTFUT drift warnings also have no roster owner.

## Goal
`data-steward` agent exists with Phase 1 (session start gate) and Phase 2 (incident triage) defined; guard script enforces allow/block rules; research-navigator invokes data-steward before graph queries and halts on non-zero exit; `RESEARCH_WORKFLOW.md` session startup protocol is complete.

## Design
**Agent definition — `.claude/agents/data-steward.md`:**

Phase 1 — Session start gate:
- Run `python scripts/bar_health.py` and `python scripts/check_feeds.py`
- Parse exit codes and output
- If any P1 violation or STALE feed: surface to researcher with specific symbol/violation, recommend action (reseed, investigate collector), halt — do NOT proceed to research loop
- If clean: confirm "Data layer clean. N symbols verified." and hand off to research-navigator

Phase 2 — Incident triage (reactive):
- Diagnose Prefect-raised errors: `SchemaError` (Alpaca schema drift), `RollAnomalyError` (bad IBKR roll), CONTFUT revision warnings
- Read Prefect logs, identify root cause, propose fix or escalate to contractor-engineer with specific context
- Can write to `data/collectors/` and `data/validation.py` for minor schema contract updates
- Cannot touch: `strategies/`, `research/`, graph schema, champion lifecycle commands

**Guard script — `.claude/scripts/agent-data-guard.sh`:**
- ALLOW: `python scripts/bar_health.py`, `python scripts/check_feeds.py`, `qw query`, ArcticDB reads, Prefect log reads
- ALLOW writes to: `data/collectors/`, `data/validation.py`, `scripts/`
- BLOCK: `qw record --bundle`, `qw abort`, `qw degrade`, `qw retire`, `qw champion`, `qw monitor`, `qw promote`
- BLOCK: `python -m research.*`
- BLOCK: writes outside allowed paths
- BLOCK: `git commit`, `git push`

**research-navigator update:**
Phase 1 of research-navigator must explicitly invoke data-steward as a pre-step before graph queries. If data-steward exits non-zero: research-navigator does not proceed to graph state synthesis.

## In Scope
- `.claude/agents/data-steward.md` — new agent definition (Phase 1 + Phase 2)
- `.claude/scripts/agent-data-guard.sh` — new guard script with allow/block rules
- `.claude/agents/research-navigator.md` — update Phase 1 to invoke data-steward before graph queries
- `docs/RESEARCH_WORKFLOW.md` — complete `## Session Startup` section: data-steward invocation → bar_health.py + check_feeds.py → decision gate → research-navigator

## Repo Touchpoints
- `.claude/agents/data-steward.md` — new; Phase 1 and Phase 2 as described
- `.claude/scripts/agent-data-guard.sh` — new; allow/block rules as described
- `.claude/agents/research-navigator.md` — update Phase 1: invoke data-steward first; halt if non-zero
- `docs/RESEARCH_WORKFLOW.md` — complete startup protocol section

## Acceptance Criteria
- [ ] `.claude/agents/data-steward.md` exists with Phase 1 and Phase 2 defined
- [ ] `.claude/scripts/agent-data-guard.sh` enforces allow/block rules above
- [ ] research-navigator Phase 1 invokes data-steward before graph queries; halts if data-steward exits non-zero
- [ ] `RESEARCH_WORKFLOW.md` `## Session Startup` section is complete: data-steward invocation → bar_health.py + check_feeds.py → decision gate → research-navigator
- [ ] Manual test: introduce a P1 bar violation in ArcticDB (e.g. write a duplicate timestamp) → data-steward surfaces it, research session halts

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: data-steward.md exists with Phase 1 + Phase 2
- type: file_check
- cmd: `grep -n "Phase 1\|Phase 2" .claude/agents/data-steward.md`
- expect_contains: "Phase 1"
- expect_contains: "Phase 2"
- expect_exit: 0

### AC2: guard script enforces block rules
- type: file_check
- cmd: `grep -n "qw record\|qw abort\|git commit" .claude/scripts/agent-data-guard.sh`
- expect_contains: "BLOCK"
- expect_exit: 0

### AC3: research-navigator invokes data-steward
- type: file_check
- cmd: `grep -n "data-steward" .claude/agents/research-navigator.md`
- expect_contains: "data-steward"
- expect_exit: 0

### AC4: RESEARCH_WORKFLOW.md startup section complete
- type: file_check
- cmd: `grep -n "bar_health\|check_feeds\|data-steward" docs/RESEARCH_WORKFLOW.md`
- expect_contains: "bar_health"
- expect_contains: "check_feeds"
- expect_exit: 0

### AC5: manual test — P1 violation halts session
- type: integration
- cmd: manual — write duplicate timestamp to ArcticDB test symbol, invoke data-steward, verify halt message with symbol name
- expect: session halts with specific symbol + violation in output
