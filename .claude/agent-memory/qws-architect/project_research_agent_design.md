---
name: Research agent architecture decision
description: Two-agent design (research-navigator opus + trial-engineer sonnet) for Epic 8 Research Agent Loop
type: project
---

Two research agents decided 2026-04-11:
- `research-navigator` (opus): ideation, graph queries, hypothesis mgmt, session summaries. Cannot run backtests.
- `trial-engineer` (sonnet): strategy code, trial scripts, backtest execution, result ingestion. Cannot interpret results or suggest directions.

Authority split: navigator reasons, trial-engineer executes. No agent curates champions — Will decides all promotions.

Epic 8 — Research Agent Loop is the container. Blocked on Epic 7 completion (FormerChampion + OpenAI curation).

Guard hooks enforce separation: `agent-research-guard.sh` blocks backtest execution for navigator, `agent-trial-guard.sh` blocks OMS/risk/promotion for trial-engineer.

**Why:** Prevents context pollution (graph reasoning vs code generation), matches model cost profiles, preserves MANIFESTO authority boundaries.

**How to apply:** All future research agent stories belong to Epic 8. Any changes to guard hooks must maintain the navigator-cannot-execute / trial-engineer-cannot-interpret boundary.
