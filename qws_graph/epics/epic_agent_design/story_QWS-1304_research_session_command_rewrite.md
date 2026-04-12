# Story 4 — Research Session Command Rewrite

## ID
QWS-1304

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1302 (navigator built + tested), QWS-1303 (trial-engineer built + tested), manual session run validating handoff contract

## Summary
Rewrite `/research-session` command to orchestrate navigator + trial-engineer agents instead of being a manual-execution protocol. Scope determined after one real session using QWS-1302 + QWS-1303.

## Problem
Current `/research-session` command (6 phases) is a manual-execution protocol for a solo researcher. After QWS-1302 and QWS-1303 exist, the command must orchestrate two agents instead of having the researcher run every step manually. Cannot be correctly written until navigator and trial-engineer output formats are known from real usage.

## Goal
After this story, `/research-session` orchestrates navigator + trial-engineer. Researcher approves each handoff. No manual query running. Navigator produces session brief → researcher picks direction → trial-engineer generates script → researcher approves run.

## Design
- Do not speculate on orchestration patterns before QWS-1302 + QWS-1303 are run in a real session
- Scope of rewrite = orchestration wiring only. Research loop itself unchanged.
- Handoff contract (navigator → trial-engineer) must be documented in command file; contract text comes from post-session findings
- Phase mapping (target, may adjust after manual session):
  - Phase 1 (start) → spawn navigator
  - Navigator produces session brief → researcher picks direction
  - Phase 2 (direction chosen) → spawn trial-engineer with direction context
  - Trial-engineer writes script → researcher reviews and approves run
  - Post-run → navigator Phase 4 (session wrap)

## In Scope
- `.claude/commands/research-session.md` — full rewrite to orchestrate navigator + trial-engineer
- Handoff contract section in command file documenting what context passes from navigator to trial-engineer

## Out of Scope
- Changing research loop logic
- Modifying navigator or trial-engineer agent files (those are frozen after QWS-1302/1303)
- Adding new query presets or graph schema changes
- Automated direction selection (researcher approves every handoff)

## Repo Touchpoints
- `.claude/commands/research-session.md` — rewrite (single file touched)

## Acceptance Criteria
- [ ] `.claude/commands/research-session.md` rewritten — no manual query steps; all screening delegated to navigator
- [ ] Command file documents navigator spawn point and expected output format (session brief)
- [ ] Command file documents trial-engineer spawn point and input contract (what context passes from navigator)
- [ ] Command file documents handoff contract explicitly: fields passed from navigator to trial-engineer
- [ ] Researcher approval gate documented at: direction pick, script review, run approval
- [ ] Old 6-phase manual protocol removed; new phase structure matches post-session findings
- [ ] Command file tested: run one full session end-to-end with both agents; no manual query steps required

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green (where applicable)
- [ ] Story marked CLOSED
