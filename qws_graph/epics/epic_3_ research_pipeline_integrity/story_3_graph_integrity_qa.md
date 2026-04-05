# Story 3 — Graph Integrity QA Script

## ID
# QWS-0303

## Status
CLOSED

## Priority
P3 — Maintainability. As the champion count grows, a manual Cypher check in the browser
is not scalable. A shell script that validates structural invariants via `qw query` catches
regressions from ingestion layer changes, parser format drifts, or schema migrations before
they silently corrupt downstream research.

## Summary
A `research/bin/qa_graph_integrity.sh` script that validates graph health by checking
**structural invariants** — not hardcoded expected values. Expected values change with every
new run; structural invariants (all Champions have flat metrics, no orphaned nodes, portfolio
query returns a result) do not.

## Design Principles
- No hardcoded metric thresholds (return, Sharpe, etc.) — these change with every ingest.
- Checks through `qw query` CLI, not `neo4j-admin` or raw Bolt — stays in the same auth
  surface as the rest of the toolchain.
- Exits non-zero on first failure. Designed to be called from a pre-push hook or CI.
- Depends on Story 2 presets (`portfolio_alpha`, `trace_champion`) being present.

## Checks

| Check | Command | Pass condition |
|---|---|---|
| Graph is reachable | `qw query --name recent_champions --json` | Exit 0 |
| At least one Champion exists | same | `length >= 1` |
| All Champions have flat metrics | Cypher via `qw query --name portfolio_alpha` | `avg_sharpe != null` |
| Fragility report runs without error | `qw query --name fragility_report --json` | Exit 0 |
| Trace resolves for latest champion | `qw query --name trace_champion` | `strategy_id` present |

## Script Location
`research/bin/qa_graph_integrity.sh` — alongside all other research runners, picked up
by the git-root-anchored preamble pattern.

## In Scope
- `research/bin/qa_graph_integrity.sh` — new script, git-root-anchored preamble, `jq` for
  JSON assertions.

## Out of Scope
- Pre-push git hook wiring (separate ops task).
- Checks for Run or Config node completeness (Story 4 / Config-Run schema split scope).
- Automated scheduling (manual for now).

## Dependencies
- Story 2 (QWS-0302) must be implemented — `portfolio_alpha`, `fragility_report`,
  `trace_champion` presets must exist.
- `jq` must be installed (`brew install jq`).

## Repo Touchpoints
- `research/bin/qa_graph_integrity.sh` — new file

## Acceptance Criteria
- [x] Script exits `0` on a healthy graph with at least one Champion.
- [x] Script exits non-zero when Neo4j is unreachable (connection error propagates from `qw`).
- [x] `avg_sharpe` null check fails if flat metrics are absent from Champion nodes.
- [x] Script follows the git-root-anchored preamble; runs correctly from any CWD.
- [x] No hardcoded expected metric values anywhere in the script.

## Definition of Done
- [x] `research/bin/qa_graph_integrity.sh` created and executable.
- [x] Script passes against the current graph state (at least one Champion with flat metrics).
