Run automated lifecycle for all stories in QuantWorkstation epic: $ARGUMENTS

Invoke skill: caveman

This skill runs in the **main session** as orchestrator. Spawn a fresh lead-engineer agent per story.

## Step 0 — Strategic validation (qws-architect, Opus)
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
1. Verify Neo4j reachable (`bolt://127.0.0.1:7687`) → ABORT if not
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
Report final status: CLOSED | BLOCKED | FAILED with details.
```

### 3d — Process result
- **CLOSED** → `make to-release` (pushes feature, merges to release, pushes release)
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
```

## Step 5 — Final report
```
## Epic $ARGUMENTS — Automation Report

### Completed (CLOSED)
- QWS-XXXX: <summary>

### Needs Attention
- QWS-ZZZZ: <failure details>

### Skipped (blocked by failures)
- QWS-VVVV: blocked on QWS-ZZZZ

### QA Review
[qa-executor findings]
```

## Failure policy
- Story A fails, B depends on A → skip B
- Story A fails, B independent → proceed with B
- Never retry a failed story automatically — needs-attention list for Will