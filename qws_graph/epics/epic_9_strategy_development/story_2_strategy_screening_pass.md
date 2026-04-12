# Story 2 — Strategy Screening Pass

## ID
QWS-0902

## Status
READY

## Blocked On
QWS-0901

## Summary
Before each new strategy idea, use `qw query --name recent_champions` and
`qw query --name list_aborted` as prescribed. Run a parameter sweep on one promising
strategy. Document promotion candidates found, aborted directions, and whether the
redundancy check caught meaningful duplicates.

## Goal
Validate that the screening workflow actually prevents redundant research. The researcher
deliberately checks the graph before each idea — not after. Document whether the
redundancy tools surfaced useful context or were ignored.

## Session Requirements
- `qw query --name recent_champions` run before each new idea
- `qw query --name list_aborted` run before each new idea
- One parameter sweep run using `research/experiments/sweep.py` or equivalent
- Sweep results ingested via `qw record --bundle`

## Deliverables
- Observation log written to `docs/research_sessions/session_0902.md`
- Log covers:
  - Promotion candidates identified (if any)
  - Aborted directions flagged by `list_aborted` before starting
  - Whether `check_redundancy` / `similar_hypotheses` caught anything useful
  - Sweep result summary (parameters tested, range, best IS Sharpe)
  - Any workflow friction specific to the sweep path

## Out of Scope
- Promoting a Champion (not required — just run the screening workflow)
- Fixing redundancy tool gaps found — log them

## Acceptance Criteria
- [ ] `recent_champions` and `list_aborted` queries run before each new idea
- [ ] One parameter sweep completed and ingested via `qw record --bundle`
- [ ] `docs/research_sessions/session_0902.md` written with observation log
- [ ] Log documents whether redundancy check was useful, neutral, or missed something

## Definition of Done
- [ ] Sweep results in graph (visible via `qw query --name recent_champions` or `promotion_candidates`)
- [ ] session_0902.md committed to repo
- [ ] Redundancy check quality assessed and documented
- [ ] Story marked CLOSED
