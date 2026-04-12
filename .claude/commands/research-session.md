# Research Session Protocol

6-phase structured research session. Execute phases in order. STOP at Phase 4 and Phase 5 gates.

---

## Phase 1 — Context Load

Read in order (silent — no output to Will):
1. `docs/MANIFESTO.md`
2. `docs/PROVENANCE_ENGINE.md`
3. `docs/RESEARCH_WORKFLOW.md`

---

## Phase 2 — Graph State

Run each query. On `PresetNotFound`: skip with inline warning, continue to next query.

```
qw query --name recent_champions
qw query --name former_champions
qw query --name list_aborted
qw query --name promotion_candidates
```

Collect all output for Phase 4 Session Brief.

---

## Phase 3 — Ideas Scan

List `research/ideas/*.md`. Parse frontmatter for each file. Collect files where `status: raw`.
If directory empty or no raw files: note "No unprocessed ideas."

---

## Phase 4 — Session Brief

Output to Will:

```
## Session Brief — YYYY-MM-DD

### Active Champions
| champion_id | strategy | sharpe | oos_status |
|---|---|---|---|
<rows from recent_champions>

### Former Champions
| champion_id | strategy | cause_of_death | retired_date |
|---|---|---|---|
<rows from former_champions, or "None">

### Promotion Candidates
| strategy | evidence_score | tier | corr_gate |
|---|---|---|---|
<rows from promotion_candidates, or "None">

### Unprocessed Ideas
<list: filename | source | one-line body preview>
or "None"

### Recent Runs (last 5)
| run_id | strategy | sharpe | n_trades | outcome |
|---|---|---|---|---|
<rows or "No recent runs">
```

**STOP. Wait for Will's direction before proceeding.**

---

## Phase 5 — Direction

Accept one of two modes:

### Mode A: Novel Direction
Will states a new idea or selects an unprocessed idea from the brief.

1. Run redundancy check:
   ```
   qw check_redundancy "<proposed hypothesis text>"
   ```
2. If redundant match found:
   - State: similar hypothesis ID, strategy, cause-of-death
   - Ask Will to confirm override before proceeding
3. If novel (or override confirmed):
   ```
   qw record --hypothesis "<text>" --source user
   ```
4. If pivot from existing node — BRANCHED_FROM is non-optional:
   - State source node ID (champion, former champion, or aborted strategy)
   - State explicit rationale: what metric or failure drives the direction change
   - Proposed edge will be created: `BRANCHED_FROM <source_id> rationale="<text>"`
5. **STOP. Show Will:**
   - Hypothesis ID
   - Redundancy check result
   - BRANCHED_FROM edge (if pivot)
   - Ask: "Approve spawning trial-engineer for this hypothesis? (yes/no)"
6. On approval only: spawn trial-engineer with:
   - Hypothesis ID
   - Strategy direction (instrument, timeframe, logic description)
   - Any regime or parameter constraints discussed

### Mode B: Review Direction
Will says "review" or asks "what have we tried on X."

Surface from graph:
- Related champions and their metrics
- Related former champions and cause-of-death
- Aborted strategies in the same family
- Parameter stability data if available

No new trials. No hypothesis logging. Produce structured output, stop.

---

## Phase 6 — Post-Session

After trial-engineer completes (or if session ends without running a trial):

Output:

```
## Session Summary — YYYY-MM-DD

### Trials Run
| trial_id | strategy | sharpe_IS | n_trades | passed_dual_hurdle |
|---|---|---|---|---|
<rows or "No trials run this session">

### Champion Changes
<list any promotions, degradations, or retirements this session, or "None">

### Unfinished Ideas
<list ideas discussed but not yet logged as Hypotheses>

### Suggested Next Pivot
Source node: <champion_id or former_champion_id or hypothesis_id>
Direction: <one sentence>
BRANCHED_FROM rationale: <specific metric or failure reason — not "didn't work">
```

Write any unfinished ideas to `research/ideas/YYYY-MM-DD-<slug>.md` with `status: raw`.
