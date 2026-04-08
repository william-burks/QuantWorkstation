# Epic 4 — Workflow Utility

## Objective
Add the small set of commands and queries that close the remaining gaps in the
research-to-decision loop — without over-engineering the graph into a decision authority
it doesn't need to be.

## Why it exists
After Epic 3, the graph has clean, consistent data and a verified ingest pipeline. The
remaining friction is in the decision loop:

1. There is no way to record OOS validation outcomes without re-ingesting a markdown file.
2. A run that clears the professional tier produces no signal at ingest time — the operator
   has to manually inspect HTML output to notice it.
3. There are no query presets that answer "what do I need to do next?" — only historical
   queries.
4. The dual-hurdle significance gate (trade count + active-window frequency) is not enforced
   at ingest time — a low-frequency strategy can pass the trade count floor and look valid.
5. Research constraints (Sharpe targets, frequency floor, holding limit) are hardcoded in
   `standards.py` and not queryable by any MCP client.

This epic closes all five gaps and stops there.

## What this epic is NOT
- Not a "graph-primary decision workflow" architectural migration.
- Not a cutover from file-based to graph-based authority. Files remain canonical research
  artifacts; the graph remains the index and query surface.
- Not a state machine formalization. The existing Champion model already encodes the
  lifecycle implicitly. Adding `workflow_models.py` on top of it would be comments as code.
- Not a graph-to-file export system. That would invert the clean Files → Graph flow for
  no operational benefit.

## Scope
- One new `qw record` mode: `--oos` to record OOS outcomes on Champion nodes.
- One post-ingest hook: print a promotion candidate notice when a run clears the
  dual-hurdle gate (trade count + active-window frequency).
- Three new `qw query` presets: `list_oos_pending`, `list_aborted`, `promotion_candidates`.
- Four new Run properties at ingest time: `active_window_frequency`, `duty_cycle`,
  `first_trade_ts`, `last_trade_ts`. Runner scripts extended to emit timestamp columns.
- One singleton `ResearchTarget` node: `qw seed --targets` and `research_targets` preset.
- Deprecation of two redundant presets: `rank_by_evidence`, `trace_champion`.

## Stories in execution order
1. `QWS-0402` `closed/story_1_oos_outcome_tracking.md` — `qw record --oos` command — **CLOSED**
2. `QWS-0407` `closed/story_4_significance_gate_properties.md` — frequency gate properties on Run — **CLOSED**
3. `QWS-0406` `story_3_workflow_query_presets.md` — query presets + deprecations (Phase A unblocked; Phase B gated on QWS-0407) — **BLOCKED**
4. `QWS-0405` `story_2_promotion_alerts.md` — post-ingest promotion candidate notice — **BLOCKED on QWS-0407**
5. `QWS-0408` `closed/story_5_research_target_node.md` — ResearchTarget singleton node — **CLOSED**

## Dependencies
- Epic 3 complete (graph has clean, consistent Champion and Run nodes).
- QWS-0407 must close before QWS-0405 can be implemented (`active_window_frequency` property
  and `MIN_ACTIVE_WINDOW_FREQUENCY` constant both required).
- QWS-0406 Phase B (`promotion_candidates` preset) gated on QWS-0407.
- QWS-0402 should close before `staleness_report` is removed (Phase C of QWS-0406).

## Cancelled stories
The following stories from the original Epic 4 scope were cancelled as over-engineered
for the current context. They are preserved in `qws_graph/epics/cancelled_stories/` for
reference.

| ID | Story | Reason |
|----|-------|--------|
| QWS-0401 | Decision-State Model | Formalizes what the data model already encodes implicitly |
| QWS-0403 | Graph-to-File Exports | Inverts the canonical Files → Graph flow; creates a two-masters problem |
| QWS-0404 | Cutover Guardrails | "Cutover" is a corporate IT concept; in a solo lab it's a habit change, not a playbook |

## Exit Criteria
- OOS outcomes can be recorded with a single CLI command (`qw record --oos`).
- A qualifying run at ingest time produces a visible promotion notice (dual-hurdle gate enforced).
- `qw query --name list_oos_pending`, `list_aborted`, and `promotion_candidates` all return
  actionable results from the live graph.
- `Run.first_trade_ts` and `Run.last_trade_ts` are required CSV columns; missing either fails parse.
- `Run.active_window_frequency` is populated on all new ingest runs (null only on zero-duration edge case).
- `Run.duty_cycle` is populated when `backtest_start`/`backtest_end` are emitted by the runner; null otherwise.
- `qw seed --targets` and `qw query --name research_targets` are functional.