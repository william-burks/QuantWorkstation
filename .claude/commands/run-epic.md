Run automated lifecycle for all stories in QuantWorkstation epic: $ARGUMENTS

Format: `/run-epic <epic_number>` or `/run-epic <epic_number> <story_id>` to resume from a specific story.
Format: `/run-epic <epic_number> qa` to skip to Step 5 (post-epic QA only).
Format: `/run-epic <epic_number> qa audit` to run QA with full audit report (verbose categorization).
Format: `/run-epic <story_id> audit` to run single story + verbose lead-engineer audit (e.g. `/run-epic QWS-0801 audit`).

This skill runs in the **main session** as orchestrator. Spawn a fresh lead-engineer agent per story.

## Step 0 — Check for resume

**If first argument matches `QWS-\d+` and second argument is `audit`** (e.g. `/run-epic QWS-0801 audit`):
1. Set STORY_ID = first argument, AUDIT_MODE_LE = verbose
2. Identify release branch: `git branch | grep release/ | sort -V | tail -1`
3. Extract epic number from story ID (e.g. QWS-0801 → epic 8)
4. Skip Steps 0a, 1, 2, 3, 4, 5 entirely
5. Jump directly to **Step 4-audit**

If second argument is `qa` (e.g. `/run-epic 6 qa`):
1. Skip Steps 0a through 4 entirely
2. Identify release branch: `git branch | grep release/ | sort -V | tail -1`
3. Check if third argument is `audit` — if yes, set AUDIT_MODE=verbose; otherwise AUDIT_MODE=quiet
4. Jump directly to Step 5 (post-epic QA)

If a story ID is provided (e.g. `/run-epic 6 QWS-0602`):
1. Read `/tmp/run_epic_$EPIC_progress.md` — verify epic matches
2. Skip Steps 0a, 1, and 2 (pre-flight, architect, execution plan)
3. Identify release branch from progress file
4. Jump to Step 3 starting at the specified story ID
5. Stories before the resume point are treated as already complete (use progress file status)

If no story ID → full run from Step 0a.

## Step 0a — Pre-flight check (product-analyst, Haiku)
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

## Step 2 — Build execution plan
1. Read `qws_graph/epics/INDEX.md` — find all stories for epic $ARGUMENTS
2. Read `docs/BACKLOG_ALIGNMENT.md` — dependencies, status
3. **GATE:** Any story `draft` → STOP. Report draft story IDs and wait for user decision.
4. Filter to `ready` stories only (skip CLOSED, TESTING)
5. Sort by dependencies (Blocked On column) — topological order
6. Present plan to user, wait for confirmation before proceeding

## Step 2b — Initialize progress file
Write `/tmp/run_epic_$EPIC_progress.md`:
```markdown
# Epic $EPIC — Run Progress
release_branch: <release branch>
started: <timestamp>

| Story | Status | Summary |
|-------|--------|---------|
| QWS-XXXX | PENDING | |
| QWS-YYYY | PENDING | |
```

## Step 3 — Pre-flight
1. Verify Neo4j reachable: `make -C qws_graph neo4j-status` → ABORT if not
2. Identify latest release branch: `git branch | grep release/ | sort -V | tail -1`
3. `git checkout <release branch> && git pull origin <release branch>`
4. `qw seed --demo`
5. `make test` — confirm clean baseline

## Step 4 — Per-story execution
For each ready story in dependency order:

### 4a — Verify story type
Read the story file. Check the `## Type` field.
- `research` or `docs` → **ABORT this story.** Print: `QWS-XXXX skipped — type=<type> not implemented in run-epic. Proceed manually.` Mark as SKIPPED in progress file. Do NOT branch or spawn any agent. Continue to next story.
- `code`, `schema`, `infra`, or missing → proceed to 4b.

### 4b — Verify dependencies
All dependencies must be CLOSED. If not → skip story + mark dependents skipped.

### 4c-branch — Branch
```
make feature-branch STORY=$STORY_ID
```

### 4c — Spawn A: implement + verify
**Pre-arm guards before spawning** (ensures sentinel is active from the agent's first tool call):
```
make prime-agent
```
Prompt:
```
For story <STORY_ID>:
1. Read and execute .claude/commands/implement-story.md for <STORY_ID>
2. Read and execute .claude/commands/verify-story.md for <STORY_ID>
Follow the command files exactly — including all git commit steps (impl, fail, fix, test).
The audit trail depends on these commits existing.
Return max 5 lines: TESTING | BLOCKED | FAILED — one-line summary — any blocker detail.
Full detail lives in git commits. Do not return test output or diffs.
```

### 4c-result — Route Spawn A outcome
- **TESTING** → proceed to Spawn B (close)
- **BLOCKED | assumption | \<question\>** → check `.claude/agent-memory/lead-engineer/` for an existing ruling on this question first. If found, write to `/tmp/ruling_<STORY_ID>.txt` and re-spawn Spawn A directly — skip architect entirely.
  If not found → spawn qws-architect (Opus):
  ```
  Read .claude/commands/answer-assumption.md and execute for: <question>
  Write full ruling to /tmp/ruling_<STORY_ID>.txt in answer-assumption format.
  Return max 3 lines: CONFIRMED|REJECTED|ALTERNATIVE — one-line ruling — one-line action.
  ```
  Re-spawn Spawn A:
  ```
  Read /tmp/ruling_<STORY_ID>.txt. Apply ruling and resume implementation of <STORY_ID>.
  After story reaches TESTING: reason about what this assumption revealed — a schema constraint,
  design boundary, or provenance rule — and write that principle to
  .claude/agent-memory/lead-engineer/. Record the insight, not the Q&A.
  Bad: "SUPERSEDED_BY chosen for QWS-XXXX"
  Good: "Provenance engine separates lineage (SUPERSEDED_BY) from consolidation (MERGED_INTO) — misuse breaks lineage traversal"
  Delete /tmp/assumption_<STORY_ID>.txt and /tmp/ruling_<STORY_ID>.txt after memory is saved.
  ```
  Max 1 assumption resolution per story → second BLOCKED | assumption → needs-attention
- **BLOCKED/FAILED** → add to needs-attention list, mark dependent stories skipped

### 4c-close — Spawn B: close only (product-owner agent)
Prompt:
```
For story <STORY_ID>:
Read and execute .claude/commands/close-story.md for <STORY_ID>
Follow the command file exactly — including all git commit steps.
Return max 3 lines: CLOSED | BLOCKED | FAILED — one-line summary — any blocker detail.
```

### 4d — Process Spawn B result
- **CLOSED** → `make to-release` (pushes feature, merges to release, pushes release)
- **BLOCKED/FAILED** → add to needs-attention list, mark dependent stories skipped

### 4e — Update progress file + continue loop
After each story completes (any outcome), update `/tmp/run_epic_$EPIC_progress.md`:
- Set story row to `CLOSED`, `BLOCKED`, `FAILED`, or `SKIPPED` with one-line summary

**Do NOT wait for user input. Immediately proceed to the next story in the list (back to Step 4a).**
Only stop the loop when:
- All stories are processed → proceed to Step 5
- A story is BLOCKED/FAILED and has dependents that must be skipped → skip dependents, then continue with remaining independent stories
- No remaining stories → proceed to Step 5

Print one line between stories: `QWS-XXXX CLOSED. N/M complete. Continuing → QWS-YYYY`

This file is the resume checkpoint. If the session dies, `/run-epic $EPIC QWS-YYYY` picks up here.

## Step 4-audit — Single-story lead-engineer audit (only when AUDIT_MODE_LE=verbose)

This entire section runs ONLY when dispatched from Step 0 via `/run-epic QWS-XXXX audit`.
It implements: run one story, audit the lead-engineer trace, offer investigate loop.

### 4-audit-a — Generate run_id
```
date -u +%Y%m%dT%H%M%S
```
Save output as RUN_ID.

### 4-audit-b — Clean stale traces + hook smoke test
```
rm -f /tmp/agent-trace-lead-engineer-*.jsonl 2>/dev/null || true
```

**Hook smoke test — verify guards fire for subagents before burning a full run:**
1. Reset read tracker: `rm -f /tmp/agent-read-tracker/store.py 2>/dev/null || true`
2. Spawn minimal lead-engineer agent:
   ```
   You must use the Read tool for each step. Do not use memory or prior knowledge.
   Step 1: Read qws_graph/research/graph/store.py lines 1-5. Report the exact first line of the docstring.
   Step 2: Read qws_graph/research/graph/store.py lines 1-5 again. Report the exact first line.
   Step 3: Read qws_graph/research/graph/store.py lines 1-5 a third time. Report ALLOWED (got content) or BLOCKED (got error).
   Return exactly 3 lines.
   ```
3. If Step 3 = **BLOCKED**: hooks working — proceed to 4-audit-c.
4. If Step 3 = **ALLOWED**: hooks not firing for subagents. **STOP.** Check `.claude/settings.json` PreToolUse hooks section and verify scripts are executable: `ls -la .claude/scripts/agent-*.sh`. Fix before retrying.

### 4-audit-c — Branch + Spawn A (implement + verify)
```
make feature-branch STORY=$STORY_ID 2>/dev/null || git checkout feature/$(REL_VER)/$STORY_ID
```
Spawn lead-engineer agent (Spawn A — implement + verify only):
```
For story <STORY_ID>:
1. Read and execute .claude/commands/implement-story.md for <STORY_ID>
2. Read and execute .claude/commands/verify-story.md for <STORY_ID>
Follow the command files exactly — including all git commit steps (impl, fail, fix, test).
The audit trail depends on these commits existing.
Return max 5 lines: TESTING | BLOCKED | FAILED — one-line summary — any blocker detail.
Full detail lives in git commits. Do not return test output or diffs.
```

### 4-audit-d — Process Spawn A result + move trace + replay
Record story outcome (TESTING / BLOCKED / FAILED).

If BLOCKED with assumption: follow same assumption resolution as Step 4c-result. Re-spawn Spawn A.
If BLOCKED/FAILED: record for final report.

Move the trace file to a story-keyed name:
```
mv /tmp/agent-trace-lead-engineer-*.jsonl /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl
```

**Trace replay — project guard impact before full qa-auditor run:**
```
source .venv/bin/activate && python .claude/scripts/trace-replay.py /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl --verbose
```
Report the summary line to user: `Replay: N read blocks, M bash-grep blocks, P search blocks = T total projected savings`
This shows what guards would eliminate in the NEXT run without spawning another agent.
If total projected savings = 0 and waste was high → guards still not firing; re-run smoke test before retrying.

### 4-audit-e — Spawn qa-auditor (verbose)
1. Find trace:
```
ls /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl
```
2. Ensure CSV exists:
```
mkdir -p docs/agent-metrics
```
If `docs/agent-metrics/lead_engineer_runs.csv` does not exist, write the header:
```
echo "run_id,timestamp,epic,story_id,branch,model,total_calls,necessary,wasted,waste_pct,verdict,acs_passed,assumption_count,top_waste_pattern" > docs/agent-metrics/lead_engineer_runs.csv
```
If `ls` fails (file not found) → **WARN: no trace file for $STORY_ID — audit skipped.** Jump to 4-audit-g.

3. Spawn qa-auditor agent (verbose):
```
Audit the agent trace at /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl
(use the actual filename found above).
Expected steps are in .claude/commands/implement-story.md.
Story: <STORY_ID>. Agent: lead-engineer. Model: sonnet. Run ID: <RUN_ID>.
Mode: verbose — full audit report.
Return:
1. A markdown table categorizing every tool call:
   | # | Tool | Target | Category | Note |
   Categories: NECESSARY, REDUNDANT, FLAILING, CONTRADICTED
2. Summary: AUDIT: <total> calls, <necessary> necessary, <wasted> wasted, <waste_pct>% waste | top: <pattern>
3. CSV row: CSV: <run_id>,<timestamp>,<epic>,<story_id>,<branch>,sonnet,<total>,<necessary>,<wasted>,<waste_pct>,<verdict>,<acs_passed>,<assumption_count>,<top_pattern>
```
4. Extract the CSV line (line starting with `CSV:`). Append to CSV:
```
echo "<CSV line without the CSV: prefix>" >> docs/agent-metrics/lead_engineer_runs.csv
```

### 4-audit-f — Present results + offer loop
Present the full categorization table and waste summary to the user.

Prompt:
```
Lead-engineer audit complete for <STORY_ID>. What next?
1. Close — accept results, proceed to final report
2. Investigate — analyze waste patterns, propose agent fixes
3. Retry — revert commits, re-run implement-story from clean state
```
Wait for user input.

**If Close:** Spawn B (close only — product-owner agent):
```
For story <STORY_ID>:
Read and execute .claude/commands/close-story.md for <STORY_ID>
Follow the command file exactly — including all git commit steps.
Return max 3 lines: CLOSED | BLOCKED | FAILED — one-line summary — any blocker detail.
```
If CLOSED: `make to-release` (pushes feature, merges to release, pushes release).
Then jump to 4-audit-g.

**If Retry:**
1. Clean story-keyed trace from this run: `rm -f /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl 2>/dev/null || true`
2. Find commits lead-engineer made this run: `git log --oneline -10`
3. Revert each agent commit: `git revert <commit> --no-edit`
4. Push reverts: `git push origin <release branch>`
5. Jump back to 4-audit-b (clean traces, re-spawn lead-engineer, re-audit)

**If Investigate:**
Spawn agent-builder agent:
```
Audit and fix agent waste. Context:

Agent: lead-engineer (definition: .claude/agents/lead-engineer.md)
Command file: .claude/commands/implement-story.md
Trace: /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl
Audit memory: ~/.claude/agent-memory/agent-builder/agent_lead-engineer.md
Categorization table from qa-auditor:
<paste the full categorization table here>

For each waste cluster (REDUNDANT/FLAILING/CONTRADICTED calls):
1. Diagnose root cause across 5 layers: spawn prompt, command file, agent memory, agent definition, hooks
2. Propose a specific fix (exact file path, exact change)
3. Present as numbered list

Also cross-check against generic patterns in ~/.claude/agent-memory/agent-builder/pattern_*.md.
If a pattern applies to this agent but isn't addressed by the audit fixes, add it to the proposal list.

Return:
- Numbered fix proposals with file paths and exact changes
- Updated efficiency table row for agent-builder audit memory
Do NOT apply fixes — return proposals only.
```

Present agent-builder's proposals:
```
Proposed fixes:
1. [file] — [change description]
2. [file] — [change description]
...
Apply all / Apply specific (e.g. 1,3) / Skip
```
- Apply selected fixes (orchestrator makes edits based on proposals)
- Update `~/.claude/agent-memory/agent-builder/agent_lead-engineer.md` with new run data
- After fixes applied, re-prompt with same 3 options (Close / Investigate / Retry)

### 4-audit-g — Cleanup + final report
```
rm -f /tmp/agent-trace-lead-engineer-$STORY_ID.jsonl 2>/dev/null || true
```

Report:
```
## <STORY_ID> — Single-Story Audit Report

### Story outcome
<CLOSED | BLOCKED | FAILED> — <summary>

### Agent Metrics (run_id: <RUN_ID>)
<full categorization table from qa-auditor>
<waste summary line>
Metrics appended to docs/agent-metrics/lead_engineer_runs.csv

### Next step
Story CLOSED → run: /close-epic <epic>
Story BLOCKED/FAILED → review findings above
```

Session ends here.

## Step 5 — Post-epic QA

### Lock gate (prevents parallel QA runs)
Each step below is ONE Bash call. Do NOT combine them.

**Step 1 — check lock:**
```
cat /tmp/qa_run.lock
```
If file exists (cat succeeds) → **STOP. ABORT.** Report the lock contents. Do NOT proceed.
If cat fails (file not found) → no lock, continue.

**Step 2 — generate run_id:**
```
date -u +%Y%m%dT%H%M%S
```
Save the output as RUN_ID. Use it for all CSV rows in this run.

**Step 3 — create lock (substitute RUN_ID and epic from above):**
```
echo "run_id=20260411T143022 epic=6 started=2026-04-11T14:30:22Z" > /tmp/qa_run.lock
```
Use the ACTUAL values — do not use shell variables or `$(...)` expansion.

**Step 4 — clean stale traces (two separate calls):**
```
rm -f /tmp/agent-trace-qa-engineer-*.jsonl 2>/dev/null || true
```
```
rm -f /tmp/agent-trace-lint-mechanic-*.jsonl 2>/dev/null || true
```

### Step 5a — QA review
```
git checkout <release branch>
git pull origin <release branch>
```
Spawn qa-engineer agent:
```
Execute .claude/commands/qa-epic.md for epic $ARGUMENTS.
You are on the release branch release/26.4.0. Review all CLOSED stories.
If lint errors found in-scope, write fixlist to /tmp/qa_epic_$ARGUMENTS_fixlist.txt. Do NOT fix lint.
Commit only fixture/seed fixes. Push if committed.
Return max 5 lines: CLEAN | LINT_FIXLIST_WRITTEN | ISSUES_REMAINING — one-line summary per issue.
Full detail lives in git commits and the QA report. Do not return test output or diffs.
```

### Step 5b — Lint fixes (only if fixlist exists)
Check if `/tmp/qa_epic_$ARGUMENTS_fixlist.txt` exists:
```
ls /tmp/qa_epic_$ARGUMENTS_fixlist.txt 2>/dev/null
```
If it exists, arm guards before spawning:
```
make prime-lint-mechanic
```
Then spawn lint-mechanic agent:
```
Read /tmp/qa_epic_$ARGUMENTS_fixlist.txt and fix every error listed.
The fixlist contains file:line:col, error code, and description for every error — it is your complete diagnosis. Do NOT run make lint before fixing. Phase A (read fixlist, read files, edit) requires zero lint runs.
You are in /Users/will/ClaudeProjects/QuantWorkstation on branch release/26.4.0.
After all fixes verified clean, run:
  git add <fixed files>
  git commit -m "qa(epic-$ARGUMENTS): post-epic QA — lint fixes"
  git push origin release/26.4.0
Return: FIXED | N files, M errors | clean: yes/no
```
If fixlist does not exist, skip to Step 5c.

### Step 5c — Automated audit + metrics
1. Find trace files for this session:
```
ls /tmp/agent-trace-qa-engineer-*.jsonl 2>/dev/null
ls /tmp/agent-trace-lint-mechanic-*.jsonl 2>/dev/null
```
2. Create metrics directory if needed:
```
mkdir -p docs/agent-metrics
```
3. If `docs/agent-metrics/qa_runs.csv` does not exist, write the header:
```
echo "run_id,timestamp,epic,branch,agent,model,total_calls,necessary,wasted,waste_pct,verdict,lint_errors_found,lint_errors_fixed,top_waste_pattern" > docs/agent-metrics/qa_runs.csv
```
4. Spawn qa-auditor agent for the qa-engineer trace. The prompt varies by AUDIT_MODE:

**If AUDIT_MODE=quiet (default):**
```
Audit the agent trace at /tmp/agent-trace-qa-engineer-<PID>.jsonl
(use the actual PID filename found in step 1).
Expected steps are in .claude/commands/qa-epic.md.
Epic: <N>. Agent: qa-engineer. Model: sonnet. Run ID: <RUN_ID>.
Mode: quiet — categorize each call, return summary only.
Return exactly two lines:
  AUDIT: <total> calls, <necessary> necessary, <wasted> wasted, <waste_pct>% waste | top: <pattern>
  CSV: <run_id>,<timestamp>,<epic>,<branch>,qa-engineer,sonnet,<total>,<necessary>,<wasted>,<waste_pct>,<verdict>,<lint_errors>,<lint_fixed>,<top_pattern>
```

**If AUDIT_MODE=verbose:**
```
Audit the agent trace at /tmp/agent-trace-qa-engineer-<PID>.jsonl
(use the actual PID filename found in step 1).
Expected steps are in .claude/commands/qa-epic.md.
Epic: <N>. Agent: qa-engineer. Model: sonnet. Run ID: <RUN_ID>.
Mode: verbose — full audit report.
Return:
1. A markdown table categorizing every tool call:
   | # | Tool | Target | Category | Note |
   Categories: NECESSARY, REDUNDANT, FLAILING, CONTRADICTED
2. Summary: AUDIT: <total> calls, <necessary> necessary, <wasted> wasted, <waste_pct>% waste | top: <pattern>
3. CSV row: CSV: <run_id>,<timestamp>,<epic>,<branch>,qa-engineer,sonnet,<total>,<necessary>,<wasted>,<waste_pct>,<verdict>,<lint_errors>,<lint_fixed>,<top_pattern>
```

5. Extract the CSV line from the auditor response (the line starting with `CSV:`). Append it to the CSV file:
```
echo "<CSV line without the CSV: prefix>" >> docs/agent-metrics/qa_runs.csv
```
6. If a lint-mechanic trace file exists, spawn qa-auditor for it too with the same run_id and AUDIT_MODE. Append its CSV row.
7. If AUDIT_MODE=quiet, include only the one-line AUDIT summary. Skip to Step 5d.

8. If AUDIT_MODE=verbose:
   - Present the full categorization table to the user
   - Show the waste summary (total, wasted, waste%, top pattern)
   - Prompt the user:
   ```
   Audit complete. What next?
   1. Close — accept results, proceed to final report
   2. Investigate — analyze waste patterns, propose fixes
   3. Retry — revert agent commits, re-run QA from clean state
   ```
   Wait for user input.

   **If Close:** proceed to Step 5d.

   **If Retry:**
   1. Find commits the agent made this run: `git log --oneline -5`
   2. Revert each agent commit: `git revert <commit> --no-edit`
   3. Push reverts: `git push origin <release branch>`
   4. Release lock: `rm -f /tmp/qa_run.lock`
   5. Jump back to Step 5 lock gate (re-acquire lock, re-spawn qa-engineer)
   After the re-run completes, return to Step 5c audit. The user can retry as many times as needed.

   **If Investigate:**
   Spawn agent-builder agent:
   ```
   Audit and fix agent waste. Context:

   Agent: <agent name> (definition: .claude/agents/<agent>.md)
   Command file: .claude/commands/qa-epic.md
   Trace: /tmp/agent-trace-<agent>-<PID>.jsonl
   Audit memory: ~/.claude/agent-memory/agent-builder/agent_qa-engineer.md
   Categorization table from qa-auditor:
   <paste the full categorization table here>

   For each waste cluster (REDUNDANT/FLAILING/CONTRADICTED calls):
   1. Diagnose root cause across 5 layers: spawn prompt, command file, agent memory, agent definition, hooks
   2. Propose a specific fix (exact file path, exact change)
   3. Present as numbered list

   Also cross-check against generic patterns in ~/.claude/agent-memory/agent-builder/pattern_*.md.
   If a pattern applies to this agent but isn't addressed by the audit fixes, add it to the proposal list.

   Return:
   - Numbered fix proposals with file paths and exact changes
   - Updated efficiency table row for agent-builder audit memory
   Do NOT apply fixes — return proposals only.
   ```

   Present agent-builder's proposals to the user:
   ```
   Proposed fixes:
   1. [file] — [change description]
   2. [file] — [change description]
   ...
   Apply all / Apply specific (e.g. 1,3) / Skip
   ```
   - Apply selected fixes (orchestrator makes the edits based on agent-builder's proposals)
   - Update agent-builder audit memory with the new run data
   - After fixes applied, re-prompt with the same 3 options (Close / Investigate / Retry)
   - User can iterate: investigate → apply fixes → retry → audit → investigate again

### Step 5d — Release lock + cleanup
Each rm is ONE Bash call. Do NOT combine them.
```
rm -f /tmp/qa_run.lock
```
```
rm -f /tmp/agent-trace-qa-engineer-*.jsonl 2>/dev/null || true
```
```
rm -f /tmp/agent-trace-lint-mechanic-*.jsonl 2>/dev/null || true
```
Always release the lock, even if earlier steps failed or errored.

## Step 6 — Final report
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

[qa-engineer findings]

### Agent Metrics (run_id: <RUN_ID>)
[AUDIT summary lines from Step 5c]
Metrics appended to docs/agent-metrics/qa_runs.csv

### Next step
QA clean → run: /close-epic $ARGUMENTS
QA issues remaining → review findings above, resolve, then run: /close-epic $ARGUMENTS
```

Clean up: `rm /tmp/run_epic_$EPIC_progress.md`

Session ends here. Close-epic is a separate cold-start.

## Failure policy
- Story A fails, B depends on A → skip B
- Story A fails, B independent → proceed with B
- Never retry a failed story — needs-attention list for Will
- Epic closure always requires human to invoke /close-epic