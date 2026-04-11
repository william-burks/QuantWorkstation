Beginning a research session for QuantWorkstation.

## Setup
Read in order:
1. `docs/MANIFESTO.md` — mission, targets, philosophy
2. `docs/PROVENANCE_ENGINE.md` — schema, MCP tools, built vs target
3. `docs/RESEARCH_WORKFLOW.md` — research loop, your role
4. `docs/BACKLOG_ALIGNMENT.md` — current sprint, unblocked stories

## Graph checks
- `qw query --name recent_champions --json`
- `qw query --name list_aborted` (skip if PresetNotFound)

## Confirm before proceeding
- Current sprint + next unblocked story
- Active Champions relevant to session topic
- Aborted strategies overlapping intended direction

## Constraints
- Sharpe >= 2.0 | holding <= 4h | optimize alpha, not win rate
- No FastAPI. `qw` CLI + MCP only.
- No [TARGET] nodes/tools from PROVENANCE_ENGINE.md
- You = Navigator. Will = Guiding Researcher + final decision-maker.

Ask: **What would you like to work on today?**