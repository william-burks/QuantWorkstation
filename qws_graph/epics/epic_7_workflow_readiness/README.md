# Epic 7 — Workflow Readiness

## Objective
Close the remaining gaps that block real research sessions from running through the full
graph loop. Three targeted stories: FormerChampion cemetery (completes redundancy check),
OpenAI curation (replaces local Llama dependency with OpenAI API, enables curation by
default), and correlation gate re-check (surfaces candidates freed up by portfolio shifts).

## Why it exists
Epics 1–6 built the forward research path (Hypothesis → trial → ingest → query). Three
gaps remain before end-to-end research sessions are reliable:
1. `former_champions` cemetery missing — redundancy check incomplete (reskin risk)
2. AI curation requires a running local Llama server — high friction, default-off
3. Correlation gate has no re-check path when portfolio composition changes

## Stories (execution order)
1. `QWS-0801` — FormerChampion Lifecycle (TESTING)
2. `QWS-0703` — OpenAI Curation Switch (READY — independent of 0801)
3. `QWS-0804` — Correlation Gate Re-check (BLOCKED on QWS-0801)

Stories 1 and 2 are independent and can be implemented in parallel.

## Dependencies
- No dependencies on backlog stories.
- QWS-0804 blocked on QWS-0801 (FormerChampion node must exist for portfolio filter).

## Exit Criteria
- `qw query --name former_champions` returns cemetery view with cause-of-death
- `qw record --kind grid_csv` runs AI curation by default via OpenAI API
- `qw record --kind grid_csv --no-analyze` skips AI curation
- `qw gate --recheck` re-evaluates correlation gate against current champion portfolio
