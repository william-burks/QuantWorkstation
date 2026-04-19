# Epic 9 — Strategy Development

## Objective

Use the system end-to-end. Run real research sessions. Document what works, what is
awkward, and what tooling gaps emerge. No code deliverables — stories are research
sessions and observation logs.

This epic exists because 8 build epics created the system. This epic uses it. The output
is not features — it is documented knowledge about the system's research fitness.

## Stories

| ID | Name | Status | Blocked On |
|---|---|---|---|
| QWS-0901 | First Research Session | READY | — |
| QWS-0902 | Strategy Screening Pass | READY | QWS-0901 |
| QWS-0903 | System Gap Audit | BLOCKED | QWS-0901, QWS-0902 |

Story files:
- `story_1_first_research_session.md`
- `story_2_strategy_screening_pass.md`
- `story_3_system_gap_audit.md`

## Note

This epic has no code deliverables. Acceptance criteria are research outputs and
documentation — not merged PRs or green tests. Stories are done when the researcher
has completed the session and written the required observation log.

## Done Criteria

- 3+ research sessions logged (QWS-0901 + QWS-0902 cover minimum)
- Each session has a written observation log (what worked, what was awkward, MCP gaps)
- `docs/epic_9_gap_audit.md` written and committed (QWS-0903)
- Backlog updated with any friction-driven story candidates surfaced by the audit
- Epic 10+ scope decisions documented as informed by gap audit findings
