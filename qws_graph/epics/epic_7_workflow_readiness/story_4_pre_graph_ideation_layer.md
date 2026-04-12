# Story 4 — Pre-Graph Ideation Layer

## ID
QWS-0704

## Status
DRAFT

## Blocked On
None

## Summary
Create `research/ideas/` as a structured holding area for half-formed observations, reading
notes, and pattern clusters before they are testable enough to log as a Hypothesis. Documents
the file convention and promotion trigger in `RESEARCH_WORKFLOW.md`.

## Problem
The current workflow starts at `log_hypothesis` — there is no documented home for the
pre-hypothesis stage. Observations from reading, market intuition, and half-formed pattern
ideas live in ephemeral notes (or nowhere). Without a convention, ideas either get lost
before they become testable, or get promoted to Hypothesis prematurely, polluting the graph
with speculative entries.

## Goal

```zsh
# Drop a raw idea into the ideation layer
vim research/ideas/2026-04-11-btc-funding-rate-regime.md

# When idea is testable + specific + non-redundant, promote:
qw record --hypothesis "funding rate inversion precedes 4h trend reversal on BTC"
# Then update research/ideas/2026-04-11-btc-funding-rate-regime.md:
#   promoted_to: hyp_abc123def456
```

## Schema
No new nodes, edges, or CLI commands. No graph changes.

## In Scope
- Create `research/ideas/` directory with `.gitkeep`
- Add "Pre-Graph Ideation" section to `docs/RESEARCH_WORKFLOW.md` documenting:
  - Purpose: structured home for raw observations before they are testable
  - File convention: `YYYY-MM-DD-<slug>.md` per idea
  - Frontmatter convention (not enforced by tooling):
    - `date` — ISO date created
    - `status` — enum: `raw | exploring | promoted | discarded`
    - `tags` — free-form list (instrument, pattern type, timeframe, etc.)
    - `promoted_to` — `hypothesis_id` value when formalized; null until then
  - Promotion trigger: Will decides when idea is testable, specific, and non-redundant
    → run `qw record --hypothesis` → update `promoted_to` in the idea file
  - Link to Hypothesis node documentation in PROVENANCE_ENGINE.md as the formalization step
- Add one example idea file in `research/ideas/` as illustration of the convention

## Out of Scope
- CLI tooling to scan or query `research/ideas/`
- New graph nodes or MCP tools
- Enforced frontmatter validation
- Auto-promotion logic

## Repo Touchpoints
- `research/ideas/` (new directory)
- `research/ideas/.gitkeep` (new file)
- `research/ideas/2026-04-11-example-idea.md` (new example file)
- `docs/RESEARCH_WORKFLOW.md` (new section)

## Acceptance Criteria
- [ ] `research/ideas/` directory exists and is tracked by git (via `.gitkeep`)
- [ ] `docs/RESEARCH_WORKFLOW.md` contains a "Pre-Graph Ideation" section documenting
  file convention, frontmatter fields, and promotion trigger
- [ ] Pre-Graph Ideation section links to Hypothesis as the formalization step
- [ ] At least one example idea file exists in `research/ideas/` demonstrating the
  frontmatter convention with realistic content

## Definition of Done
- [ ] `research/ideas/.gitkeep` committed
- [ ] Example idea file committed with valid frontmatter (date, status, tags, promoted_to)
- [ ] `docs/RESEARCH_WORKFLOW.md` Pre-Graph Ideation section written and links to
  `docs/PROVENANCE_ENGINE.md` Hypothesis node documentation
- [ ] No new nodes, CLI commands, or schema changes introduced
- [ ] Story marked CLOSED
