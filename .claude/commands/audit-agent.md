Audit agent efficiency from a tool trace. Agent name: $ARGUMENTS

Format: `/audit-agent <agent-name>` — reads the most recent tool trace for that agent and produces an efficiency report with actionable fixes.

This skill runs in the **main session** as orchestrator. Two-pass audit: Sonnet categorizes, Opus diagnoses.

## Step 0 — Locate the trace

1. Ask the user to paste the tool trace, or specify a file path containing it
2. If the user already pasted a trace in conversation, use that directly
3. Read the agent definition: `.claude/agents/<agent-name>.md` (project) or `~/.claude/agents/<agent-name>.md` (global)
4. Read the agent's memory directory if it exists: `.claude/agent-memory/<agent-name>/`
5. Identify which command file(s) the agent was executing (from triggers in agent def or spawn prompt)
6. Read those command files

## Step 1 — Categorization pass (Sonnet)

Spawn a general-purpose agent with `model: sonnet`:
```
You are auditing tool efficiency for a Claude Code agent run.

Agent definition:
<paste agent def content>

Command file(s) executed:
<paste command file content>

Tool trace:
<paste trace>

Categorize every tool call into exactly one bucket:

| Category | Definition |
|----------|-----------|
| NECESSARY | Required by the command file or essential to the task |
| REDUNDANT | Re-reads a file already in context, re-runs a passing check |
| FLAILING | Multiple similar attempts, chunked reads without grep, trial-and-error |
| CONTRADICTED | Agent did something the command file or agent def told it not to |
| MISSING | Something the command file required but the agent skipped |

Output format — a markdown table, one row per tool call:
| # | Tool | Target | Category | Note |
|---|------|--------|----------|------|

Then a summary:
- Total calls: N
- Necessary: N (X%)
- Wasted (redundant + flailing + contradicted): N (Y%)
- Missing actions: N

List each CONTRADICTED and MISSING item with the specific instruction it violates.
Do not propose fixes — just categorize.
```

## Step 2 — Diagnosis pass (main session, Opus)

Using the Sonnet categorization, perform root-cause analysis:

For each waste cluster:
1. **Spawn prompt** — did it contradict command files? Omit needed context?
2. **Command file** — were commands explicit enough? Missing grep hints for large files?
3. **Agent memory** — was memory read? Was the needed info there? Should it be seeded?
4. **Agent definition** — wrong model? Missing tool grant? Effort level wrong?
5. **File structure** — large files without grep targets? Missing indexes?

## Step 3 — Report

Present the audit in this exact format:
```
## Audit: <agent-name> on <task>

### Tool call summary
Total: N | Necessary: X | Wasted: Y (Z%)

### Waste breakdown
| Issue | Calls wasted | Root cause | Fix |
|-------|-------------|------------|-----|

### Contradictions
[spawn prompt vs command file conflicts, with line references]

### Missing actions
[required steps the agent skipped]

### Recommendations
[numbered list — specific file:line edits, not vague advice]
Each recommendation specifies:
- Which file to edit (agent def, command file, or memory)
- What to change (exact before/after or new content)
- Expected impact (calls saved, contradiction resolved)
```

## Step 4 — Apply fixes

After user reviews the report:
1. User approves specific recommendations (by number)
2. Apply edits directly — agent defs, command files, memory seeds
3. For complex agent redesigns, spawn agent-builder instead

## Step 5 — Record patterns

After every audit, write what you learned to agent-builder memory at `~/.claude/agent-memory/agent-builder/`.
Record **patterns**, not instances:
- Good: "Agents that touch PROVENANCE_ENGINE.md (800+ lines) waste 5-8 calls chunking it — add grep hints to command files"
- Bad: "lead-engineer chunked PROVENANCE_ENGINE.md 6 times during QWS-0604"

## Model allocation

| Phase | Model | Why |
|-------|-------|-----|
| Categorization (Step 1) | Sonnet | Mechanical classification — no reasoning needed |
| Diagnosis (Step 2) | Opus (main session) | Root-cause analysis requires cross-referencing multiple files |
| Fix application (Step 4) | Opus (main session) | Edits need architectural judgment |
| Pattern recording (Step 5) | Opus (main session) | Generalization from instance to pattern |
