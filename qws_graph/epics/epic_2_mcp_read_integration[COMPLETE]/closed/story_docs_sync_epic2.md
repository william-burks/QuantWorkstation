# Story — Docs Sync: README and Runbook for Epic 2

## Status
draft

## Priority
P2 — Documentation Debt. Both `README.md` and `docs/qws_graph_runbook.md` were last updated
after Epic 1. All Epic 2 capabilities (query layer, abort, family_id, significance gate,
semantic tier, MCP adapter) are undocumented. Any operator or LLM reading these files will
have an incomplete and misleading picture of the current CLI surface.

## Summary
Review every closed story in both `[COMPLETE]` epic directories and update `README.md` and
`docs/qws_graph_runbook.md` to reflect the current implemented state. No code changes.

## Inputs
- `epics/epic_1_ingestion_and_index[COMPLETE]/closed/*.md` — Epic 1 baseline (already reflected)
- `epics/epic_2_mcp_read_integration[COMPLETE]/closed/*.md` — Epic 2 additions (not yet reflected)
- `research/graph/cli.py` — current CLI surface (ground truth for command flags)
- `research/graph/query.py` — `QUERY_VIEW_REGISTRY` and `PRESET_CATALOG` (ground truth for view names)
- `research/graph/analyst.py` — semantic tier env vars and behavior
- `docs/graph_v1_contract.md` — canonical node/edge schema

## What Has Changed Since Last Doc Update

### New CLI commands (Epic 2)
| Command | Added by |
|---|---|
| `qw query` | Story 1/2 |
| `qw abort` | Churn Story 1 |
| `qw record --source-file` | Churn Story 1 |
| `qw record --all` | Churn Story 1 |
| `qw record --analyze` | Story 2 (semantic gate) |

### New graph capabilities
| Capability | Story |
|---|---|
| `family_id` on `Strategy` nodes | Churn Story 1 |
| `RunStatsSummary` node + significance gate | Churn Story 1 |
| `Strategy.status` / `Strategy.abort_reason` | Churn Story 1 |
| `Run.curator_note` | Story 2 semantic gate |
| MCP adapter `get_context_neighborhood` | Epic 2 spike + Story 3 |
| Query views (7 named views + 5 presets) | Stories 1–4 |

### New env vars
| Var | Purpose |
|---|---|
| `QW_AI_ANALYST_ENDPOINT` | Llama 4 Scout endpoint for `--analyze` |
| `QW_AI_ANALYST_MODEL` | Model override (default `Llama-4-Scout-17B-16E-Instruct`) |
| `QW_AI_PROVIDER` | Analyst provider (default `llama`) |

## Acceptance Criteria

### README.md
- [ ] "What this project does now" section updated: add query layer, abort, family_id,
      significance gate, semantic tier, MCP adapter.
- [ ] "What this project does not do in V1" section reviewed: remove items that are now
      implemented (MCP read path is implemented in Epic 2).
- [ ] Command Reference updated: `qw query` and `qw abort` documented with flags and exit codes.
- [ ] `qw record` command reference updated with `--source-file`, `--all`, `--analyze`.
- [ ] Env vars section added covering Epic 2 additions.
- [ ] Closed Story Traceability table updated with all Epic 2 closed stories.

### docs/qws_graph_runbook.md
- [ ] Day-1 Operations updated: add `qw query` usage examples for each preset.
- [ ] Day-1 Operations updated: add `qw abort` usage example.
- [ ] Day-1 Operations updated: add `qw record --source-file` ingest example.
- [ ] Day-1 Operations updated: add `--analyze` flag usage with env var prerequisite.
- [ ] Failure Modes table updated: add semantic tier unavailable, strategy not found (abort).
- [ ] Verification Checklist updated: add Epic 2 items.
- [ ] Closed Story Traceability table updated with all Epic 2 closed stories.

## In Scope
- `README.md` and `docs/qws_graph_runbook.md` only.
- Content derived from closed story ACs and `cli.py` ground truth.
- No new sections invented beyond what the closed stories establish.

## Out of Scope
- `docs/graph_v1_contract.md` (separate schema document, not a user-facing doc).
- `epics/*/README.md` files (epic-level docs, not operator docs).
- Code changes of any kind.

## Definition of Done
- [ ] README and runbook both reflect the current Epic 1 + Epic 2 implemented state.
- [ ] Traceability tables include all closed stories from both epics.
- [ ] Story marked CLOSED.

## Dependencies
- Depends on: all Epic 1 and Epic 2 stories — CLOSED.
