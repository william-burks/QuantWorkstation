# Story 1 — Research Ideas Layer

## ID
QWS-1301

## Status
READY

## Type
code

## Blocked On
QWS-HF-001 (GAP-010 fix — branched-from in one call), QWS-0905 (findings field on Hypothesis)

## Summary
Add `queued` state to Hypothesis nodes so mid-session ideas park in the graph, not flat files. One command to create + queue with lineage. One query to see what's waiting.

## Problem
Mid-session ideas get parked in `research/ideas/*.md` flat files — not in the graph. No "what's queued" query. No way to mark a hypothesis as "I want to try this" without committing to running it now. No `Run → Hypothesis` lineage for ideas that emerge from a specific trial result (GAP-001 + GAP-008).

## Goal
After this story, a researcher can:
1. Flag an existing hypothesis as `queued` — "park this, try later"
2. Log a new idea mid-session in one command with `--branched-from <run_id>` (uses `BRANCHED_FROM` edge to Run — no new edge type needed)
3. Query `qw query --name queued_hypotheses` to see all queued ideas with title, findings, branched-from context
4. Pop one from the queue when ready (update status to `raw` or `confirmed`)

## Design
- `queued` is a boolean property on `Hypothesis` node — additive, nullable, defaults false
- `--queue` flag added to `qw record --hypothesis` — sets `queued=true`
- `--branched-from <run_id or hypothesis_id>` already planned under QWS-HF-001; this story depends on that being merged
- `queued_hypotheses` preset: `MATCH (h:Hypothesis {queued: true}) OPTIONAL MATCH (h)-[:BRANCHED_FROM]->(src) RETURN h.hypothesis_id, h.title, h.findings, src.hypothesis_id, h.created_at ORDER BY h.created_at DESC`

## In Scope
- `queued` property on `Hypothesis` node
- `qw record --hypothesis <id> --queue` — set queued on existing node
- `qw record --hypothesis "<title>" --branched-from <id> --queue` — create + queue in one call
- `queued_hypotheses` query preset
- `data_dictionary.yaml` updated with `queued` property
- `RESEARCH_WORKFLOW.md` updated: graph-first parking sequence (create node before flat file)

## Out of Scope
- Priority ordering within queue (use created_at sort, no priority field)
- Queue capacity limits
- Auto-expiry of queued hypotheses
- UI or TUI for queue management

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — `record` command, `--queue` flag, `--branched-from` flag wiring
- `qws_graph/research/graph/queries/queued_hypotheses.cypher` — new preset file
- `qws_graph/research/graph/query_presets.yaml` — register `queued_hypotheses`
- `qws_graph/data_dictionary.yaml` — add `queued: bool` to Hypothesis properties
- `docs/RESEARCH_WORKFLOW.md` — parking sequence update

## Acceptance Criteria
- [ ] `qw record --hypothesis "test idea" --queue` creates Hypothesis node with `queued=true`
- [ ] `qw record --hypothesis "test idea" --branched-from <run_id> --queue` creates node + BRANCHED_FROM edge + `queued=true` in one call
- [ ] `qw record --hypothesis <existing_id> --queue` sets `queued=true` on existing node without creating duplicate
- [ ] `qw query --name queued_hypotheses` returns all `queued=true` hypotheses; result includes id, title, findings (truncated to 200 chars), branched-from id if present, created_at
- [ ] `qw query --name queued_hypotheses` returns empty result (not error) when queue is empty
- [ ] Setting `--status` on a queued hypothesis also sets `queued=false`. Dequeue by running `qw record --hypothesis --id <id> --status raw` which sets `queued=false`. No separate `--dequeue` flag.
- [ ] `data_dictionary.yaml` reflects `queued` property with type and default
- [ ] `RESEARCH_WORKFLOW.md` parking sequence updated
- [ ] `docs/PROVENANCE_ENGINE.md` Hypothesis Key Properties table updated with `queued: bool — true if hypothesis is parked for future research session`
- [ ] `docs/PROVENANCE_ENGINE.md` [TARGET] tools section updated with `queued_hypotheses` preset entry

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green (where applicable)
- [ ] Story marked CLOSED
