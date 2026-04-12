# Story 3 — System Gap Audit

## ID
QWS-0903

## Status
BLOCKED

## Blocked On
QWS-0901, QWS-0902

## Summary
After completing QWS-0901 and QWS-0902, synthesize all friction points and observations
into `docs/epic_9_gap_audit.md`. This document feeds scope decisions for Epic 10 and
beyond — it is not a code deliverable, it is a decision input.

## Goal
Produce a single structured document that captures what the system does well, where it
creates friction, what data or tooling is missing, and where the AI assistant got things
wrong. This gap audit is the primary output of Epic 9.

## Output Format

`docs/epic_9_gap_audit.md` must include:

### Sections
1. **Tooling Gaps** — CLI commands or MCP tools that are missing, broken, or poorly scoped
2. **Missing Data** — instruments, timeframes, or data sources needed but absent
3. **Workflow Friction** — steps that required workarounds or felt unnatural
4. **AI Assistant Failures** — cases where MCP tool responses were wrong, misleading, or
   unhelpful during research sessions
5. **Backlog Candidates** — specific story candidates that address the gaps above
6. **Epic Scope Implications** — which gaps should inform Epic 10, Epic 12, or new epics

## Deliverables
- `docs/epic_9_gap_audit.md` written and committed
- Backlog section of `docs/BACKLOG_ALIGNMENT.md` updated with any new story candidates
  surfaced by the audit

## Out of Scope
- Implementing fixes (this story is observation and synthesis only)
- Scoping the new stories (Will decides priority after reading the audit)

## Acceptance Criteria
- [ ] `docs/epic_9_gap_audit.md` exists with all 6 sections populated
- [ ] Each tooling gap has a specific description (not "CLI was slow" — specific command, specific failure)
- [ ] Each backlog candidate has a one-line "what it delivers" description
- [ ] BACKLOG_ALIGNMENT.md updated with new story candidates (Will reviews before adding to sprint)

## Definition of Done
- [ ] `docs/epic_9_gap_audit.md` committed
- [ ] BACKLOG_ALIGNMENT.md backlog candidates section updated
- [ ] Epic 10+ scope notes written in the audit (even if speculative)
- [ ] Story marked CLOSED
