# Story 4 — Research Session Command Rewrite

## ID
QWS-0904

## Status
DRAFT

## Blocked On
QWS-0902 CLOSED, QWS-0903 CLOSED

## Summary
Rewrite `.claude/commands/research-session.md` as a 6-phase structured protocol. Replaces
the current ad-hoc setup prompt with a deterministic sequence: context load → graph state →
ideas scan → session brief → direction + trial spawn → post-session report.

## Problem
The current `research-session.md` is a 25-line setup prompt. It loads docs and queries the
graph but produces no structured output, has no decision gate before trial execution, and
leaves no post-session artifact. Each session reinvents the workflow. With navigator and
trial-engineer agents now defined (QWS-0902, QWS-0903), the command file must orchestrate
them explicitly.

## Goal

```zsh
/research-session

# Phase 1 — Context Load (automatic)
# Phase 2 — Graph State (qw queries, warn on missing presets)
# Phase 3 — Ideas Scan (research/ideas/*.md, show status: raw only)
# Phase 4 — Session Brief (structured output)
# Phase 5 — Direction (Will picks; spawn trial-engineer if novel + approved)
# Phase 6 — Post-Session (summary report + idea files + next pivot suggestion)
```

## Protocol Specification

### Phase 1 — Context Load
Read in order:
1. `docs/MANIFESTO.md`
2. `docs/PROVENANCE_ENGINE.md`
3. `docs/RESEARCH_WORKFLOW.md`

No output to Will at this phase. Silent load.

### Phase 2 — Graph State
Run each query. On `PresetNotFound` skip with inline warning (do not abort session):
```
qw query --name recent_champions
qw query --name former_champions
qw query --name list_aborted
qw query --name promotion_candidates
```
Collect output for Session Brief.

### Phase 3 — Ideas Scan
List `research/ideas/*.md`. Parse frontmatter. Surface only files with `status: raw`.
If no raw ideas: note "No unprocessed ideas" in brief.

### Phase 4 — Session Brief
Output structured summary to Will:
```
## Session Brief — YYYY-MM-DD

### Active Champions
<table: champion_id | strategy | sharpe | oos_status>

### Former Champions
<table: champion_id | strategy | cause_of_death | retired_date>

### Promotion Candidates
<table: strategy | evidence_score | tier | corr_gate_status>

### Unprocessed Ideas
<list: filename | source | one-line body>

### Recent Runs (last 5)
<table: run_id | strategy | sharpe | n_trades | outcome>
```
STOP. Wait for Will's direction.

### Phase 5 — Direction
Accept one of:
- **Novel direction** — Will states new idea or approves an unprocessed idea:
  1. Run `qw check_redundancy` on proposed hypothesis text
  2. If redundant: flag similarity + cause-of-death, ask Will to confirm override
  3. If novel (or override confirmed): `qw record --hypothesis "<text>" --source user`
  4. If pivot from existing node: create `BRANCHED_FROM` edge — state source node +
     rationale explicitly; BRANCHED_FROM is non-optional
  5. STOP. Present hypothesis ID + redundancy result to Will.
  6. Ask: "Approve spawning trial-engineer?" — do not spawn without explicit approval.
  7. On approval: spawn trial-engineer with hypothesis ID, strategy direction, instrument,
     and timeframe.
- **Review direction** — Will says "review" or "what have we tried on X":
  Surface relevant patterns from graph queries. No new trials. No hypothesis logging.
  Report: related champions, former champions, aborted strategies, parameter stability
  if available.

### Phase 6 — Post-Session
After trial-engineer completes (or if session ends without a trial):
Output structured summary report:
```
## Session Summary — YYYY-MM-DD

### Trials Run
<table: trial_id | strategy | sharpe | n_trades | passed_gate>

### Champion Changes
<list: promoted / degraded / retired this session (if any)>

### Unfinished Ideas
<list: ideas discussed but not yet logged — write to research/ideas/ as status: raw>

### Suggested Next Pivot
<one pivot suggestion with BRANCHED_FROM rationale: "Based on [source node], suggest
[direction] because [specific metric/failure reason]">
```
Write any unfinished ideas to `research/ideas/YYYY-MM-DD-<slug>.md` with `status: raw`.

## In Scope
- `.claude/commands/research-session.md` — full rewrite

## Out of Scope
- Any graph schema changes
- Any CLI changes
- Changes to navigator or trial-engineer agent definitions (those are QWS-0902/0903)

## Repo Touchpoints
- `.claude/commands/research-session.md`

## Acceptance Criteria
- [ ] `research-session.md` contains all 6 phases in order with explicit phase headings
- [ ] Phase 2 handles `PresetNotFound` gracefully (skip + warn, do not abort)
- [ ] Phase 3 filters to `status: raw` ideas only
- [ ] Phase 4 produces structured Session Brief and stops to wait for Will's input
- [ ] Phase 5 runs redundancy check before hypothesis logging; BRANCHED_FROM is documented
  as non-optional for pivots; trial-engineer spawn requires explicit approval
- [ ] Phase 6 writes unfinished ideas to `research/ideas/` and produces next-pivot suggestion
  with BRANCHED_FROM rationale
- [ ] Old research-session.md content (25-line setup prompt) is fully replaced

## Definition of Done
- [ ] `research-session.md` rewritten as 6-phase protocol
- [ ] Manual walkthrough: run `/research-session`, verify each phase gate fires in order
- [ ] Phase 5 novel path: confirm redundancy check runs before hypothesis logged
- [ ] Phase 5 trial spawn: confirm approval gate fires before trial-engineer spawned
- [ ] Phase 6: confirm idea files written and next-pivot suggestion present
- [ ] All tests pass (`ruff check .` and `mypy --strict .` clean)
- [ ] Story marked CLOSED
