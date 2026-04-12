# Story 1 — First Research Session

## ID
QWS-0901

## Status
READY

## Blocked On
None

## Summary
Run 3 full research sessions using the complete system stack (hypothesis → trial → graph
record → query). Log a Hypothesis node for each trial. Document what worked, what felt
awkward, and any MCP tool gaps encountered.

## Goal
The researcher uses the system as built — no workarounds, no skipping steps. Each trial
follows the prescribed workflow:

1. Form a hypothesis, log it: `qw record --hypothesis`
2. Run trial script, record bundle: `qw record --bundle`
3. Query results: `qw query --name recent_champions`, `qw query --name list_aborted`
4. Write observation notes after each session

## Session Requirements
- Minimum 3 trials run through the full stack
- Each trial has a Hypothesis node in the graph before the trial runs
- `qw record --bundle` used for each trial result ingestion
- No manual Cypher writes — CLI and MCP tools only

## Deliverables
- Observation log written to `docs/research_sessions/session_0901.md`
- Log covers: what worked smoothly, what was awkward, any CLI errors or friction, any
  MCP tool gaps observed during the session
- Hypothesis nodes visible in graph via `qw query --name hypothesis_audit`

## Out of Scope
- Fixing any gaps found — log them; QWS-0903 synthesizes
- Achieving a specific Sharpe target or promoting a Champion

## Acceptance Criteria
- [ ] 3+ trials run using full stack (hypothesis → record → query)
- [ ] Hypothesis node logged before each trial
- [ ] `qw record --bundle` used for each trial (no manual writes)
- [ ] `docs/research_sessions/session_0901.md` written with observation log
- [ ] Observation log covers: workflow steps that worked, friction points, MCP gaps

## Definition of Done
- [ ] 3+ Hypothesis nodes visible in graph post-session
- [ ] session_0901.md committed to repo
- [ ] Friction points listed (not fixed — listed)
- [ ] Story marked CLOSED
