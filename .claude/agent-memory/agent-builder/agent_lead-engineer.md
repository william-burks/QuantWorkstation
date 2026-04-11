---
name: Lead-engineer audit history
description: Efficiency metrics, waste patterns, and applied fixes for the lead-engineer agent across story runs
type: project
---

## Efficiency Table

| Run | Story | Total | Necessary | Wasted | Waste% | Top Pattern | Fixes Applied |
|-----|-------|-------|-----------|--------|--------|-------------|---------------|
| 20260411T200900 | QWS-0801 | 144 | 87 | 57 | 40% | file-reread | baseline |
| 20260411T200900-retry | QWS-0801 | 228 | 111 | 117 | 51% | lint-loop | prose prohibition (FAILED) |

## Confirmed Waste Patterns

### 1. lint-loop (most expensive — 35+ calls in Run 2)
Prose prohibition "Do NOT fix ruff errors directly" failed ~100%. Agent ran `make check`/`make lint` with grep filters.
Root cause: `make lint` = ruff + mypy bundled — agent cannot run mypy without triggering ruff.

**Fix applied (structural):**
- `make lint` now ruff-only; `make typecheck` is new mypy-only target
- `agent-guard.sh` blocks: `ruff *`, `make lint`, `make check`
- `implement-story.md` lint section removed — lint deferred to QA phase
- `implement-story.md` mypy line: `mypy --strict` → `make typecheck`

### 2. file-reread (53 redundant reads across both runs)
Agent re-reads files already in context, especially story file, PROVENANCE_ENGINE.md, BACKLOG_ALIGNMENT.md.
Current mitigation: prose rules in agent def ("Once a file is Read into context, do NOT Read it again") + STOP gates.
Status: not yet solved structurally — would require read-tracking hook. Watch in next run.

### 3. MCP over-search
Multiple search_code calls for variants of the same symbol (e.g. `ChampionNode` + `class ChampionNode`).
Mitigation: one-search-per-concept rule added to implement-story.md Step 3.

## Principle Confirmed
**Prose prohibition failure rate ~100% when prohibited action is agent's default instinct.**
This applies across qa-engineer (8+ runs) and lead-engineer (2 runs).
Only structural enforcement works: hooks, guards, removing the tool/command from the agent's reach.
