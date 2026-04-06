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

These are three focused gaps. This epic closes them and stops there.

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
  professional tier.
- Two new `qw query` presets: `list_oos_pending` and `promotion_candidates`.

## Stories in execution order
1. `QWS-0402` `story_1_oos_outcome_tracking.md` — `qw record --oos` command
2. `QWS-0405` `story_2_promotion_alerts.md` — post-ingest promotion candidate notice
3. `QWS-0406` `story_3_workflow_query_presets.md` — `list_oos_pending` + `promotion_candidates` presets

Stories 2 and 3 are independent of Story 1 and can be implemented in any order.

## Cancelled stories
The following stories from the original Epic 4 scope were cancelled as over-engineered
for the current context. They are preserved in `qws_graph/epics/cancelled_stories/` for
reference.

| ID | Story | Reason |
|----|-------|--------|
| QWS-0401 | Decision-State Model | Formalizes what the data model already encodes implicitly |
| QWS-0403 | Graph-to-File Exports | Inverts the canonical Files → Graph flow; creates a two-masters problem |
| QWS-0404 | Cutover Guardrails | "Cutover" is a corporate IT concept; in a solo lab it's a habit change, not a playbook |

## Dependencies
- Epic 3 complete (graph has clean, consistent Champion and Run nodes).
- No cross-story dependencies within this epic except Story 1 must precede any
  `qw query --name list_oos_pending` returning meaningful results.

## Exit Criteria
- OOS outcomes can be recorded with a single CLI command.
- A qualifying run at ingest time produces a visible promotion notice.
- `qw query --name list_oos_pending` and `qw query --name promotion_candidates` both
  return actionable results from the live graph.
