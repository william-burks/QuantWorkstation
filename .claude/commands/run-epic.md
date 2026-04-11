Run automated lifecycle for all stories in QuantWorkstation epic: $ARGUMENTS

This skill runs in the **main session** as orchestrator. Spawn a fresh lead-engineer agent per story.

## Step 0 — Pre-flight check (product-analyst, Haiku)
Spawn product-analyst agent:
```
Read qws_graph/epics/INDEX.md and docs/BACKLOG_ALIGNMENT.md.
For epic $ARGUMENTS check:
1. Any story not `ready` (draft, TESTING, BLOCKED)?
2. Any story with unresolved dependencies (blocked-on not CLOSED)?
3. Neo4j reachable? Run: make -C qws_graph neo4j-status
4. Latest release branch name (git branch | grep release/ | sort -V | tail -1)?
Return: READY_TO_RUN | BLOCKED — one line per issue. Max 10 lines total.
```
If BLOCKED → STOP. Report issues. Do not proceed to architect or implementation.

## Step 1 — Strategic validation (qws-architect, Opus)

Spawn qws-architect agent:
```
Load: docs/MANIFESTO.md, docs/RESEARCH_WORKFLOW.md, docs/PROVENANCE_ENGINE.md, docs/BACKLOG_ALIGNMENT.md
Load: all story files for epic $ARGUMENTS in qws_graph/epics/

Validate:
1. Do these stories collectively build toward the target exocortex?
2. Any story that passes validation but points in the wrong direction?
3. Schema drift between PROVENANCE_ENGINE and story touchpoints?
4. Dependency chains circular or missing?
5. Sprint sequence optimal — does order maximize capability unlock?

Report: ALIGNED | MISALIGNED (with specific findings per story)
```
If MISALIGNED → ABORT with architect's findings. Do not proceed to implementation.

## Step 1 — Build execution plan
1. Read `qws_graph/epics/INDEX.md` — find all stories for epic $ARGUMENTS
2. Read `docs/BACKLOG_ALIGNMENT.md` — dependencies, status
3. **GATE:** Any story `draft` → STOP. Report draft story IDs and wait for user decision.
4. Filter to `ready` stories only (skip CLOSED, TESTING)
5. Sort by dependencies (Blocked On column) — topological order
6. Present plan to user, wait for confirmation before proceeding

## Step 2 — Pre-flight
1. Verify Neo4j reachable: `make -C qws_graph neo4j-status` → ABORT if not
2. Identify latest release branch: `git branch | grep release/ | sort -V | tail -1`
3. `git checkout <release branch> && git pull origin <release branch>`
4. `qw seed --demo`
5. `pytest tests/unit/ -v` — confirm clean baseline

## Step 3 — Per-story execution
For each ready story in dependency order:

### 3a — Verify dependencies
All dependencies must be CLOSED. If not → skip story + mark dependents skipped.

### 3b — Branch
```
git checkout <release branch>
git pull origin <release branch>
git checkout -b feature/<ver>/$STORY_ID
```

### 3c — Spawn lead-engineer agent
Prompt:
```
Execute full story lifecycle for <STORY_ID>:
1. Read and execute .claude/commands/implement-story.md for <STORY_ID>
2. Read and execute .claude/commands/verify-story.md for <STORY_ID>
3. Read and execute .claude/commands/close-story.md for <STORY_ID>
Return max 5 lines: CLOSED | BLOCKED | FAILED — one-line summary — any blocker detail.
Full detail lives in git commits. Do not return test output or diffs.
```

### 3d — Process result
- **CLOSED** → `make to-release` (pushes feature, merges to release, pushes release)
- **BLOCKED | assumption | \<question\>** → check `.claude/agent-memory/lead-engineer/` for an existing ruling on this question first. If found, write to `/tmp/ruling_<STORY_ID>.txt` and re-spawn lead-engineer directly — skip architect entirely.
  If not found → spawn qws-architect (Opus):
  ```
  Read .claude/commands/answer-assumption.md and execute for: <question>
  Write full ruling to /tmp/ruling_<STORY_ID>.txt in answer-assumption format.
  Return max 3 lines: CONFIRMED|REJECTED|ALTERNATIVE — one-line ruling — one-line action.
  ```
  Re-spawn lead-engineer:
  ```
  Read /tmp/ruling_<STORY_ID>.txt. Apply ruling and resume implementation of <STORY_ID>.
  After story closes: reason about what this assumption revealed — a schema constraint,
  design boundary, or provenance rule — and write that principle to
  .claude/agent-memory/lead-engineer/. Record the insight, not the Q&A.
  Bad: "SUPERSEDED_BY chosen for QWS-XXXX"
  Good: "Provenance engine separates lineage (SUPERSEDED_BY) from consolidation (MERGED_INTO) — misuse breaks lineage traversal"
  Delete /tmp/assumption_<STORY_ID>.txt and /tmp/ruling_<STORY_ID>.txt after memory is saved.
  ```
  Max 1 assumption resolution per story → second BLOCKED | assumption → needs-attention
- **BLOCKED/FAILED** → add to needs-attention list, mark dependent stories skipped

### 3e — Progress
Report: `QWS-XXXX CLOSED. N/M complete. Next: QWS-YYYY`

## Step 4 — Post-epic QA
```
git checkout <release branch>
git pull origin <release branch>
```
Spawn qa-executor agent:
```
Execute .claude/commands/qa-epic.md for epic $ARGUMENTS.
You are on the release branch. Review all CLOSED stories, commit fixes, push.
Return max 5 lines: CLEAN | ISSUES_FIXED | ISSUES_REMAINING — one-line summary per issue.
Full detail lives in git commits and the QA report. Do not return test output or diffs.
```

## Step 5 — Final report
```
## Epic $ARGUMENTS — Automation Report

### Completed (CLOSED)
- QWS-XXXX: <summary>

### Needs Attention (story failures)
- QWS-ZZZZ: <failure details>

### Skipped (blocked by story failures)
- QWS-VVVV: blocked on QWS-ZZZZ

### QA Verdict
CLEAN | ISSUES_FIXED | ISSUES_REMAINING

[qa-executor findings]

### Next step
QA clean → run: /close-epic $ARGUMENTS
QA issues remaining → review findings above, resolve, then run: /close-epic $ARGUMENTS
```

Session ends here. Close-epic is a separate cold-start.

## Failure policy
- Story A fails, B depends on A → skip B
- Story A fails, B independent → proceed with B
- Never retry a failed story — needs-attention list for Will
- Epic closure always requires human to invoke /close-epic