Tune agent from accumulated audit findings: $ARGUMENTS

Format: `/tune-agent <agent-name>` — apply all generic patterns and agent-specific findings to harden the agent.

## Step 0 — Load context

Read ALL of these (parallel where possible):
1. Agent definition: `.claude/agents/$ARGUMENTS.md`
2. Agent memory index: `.claude/agent-memory/$ARGUMENTS/MEMORY.md`
3. Agent-specific audit profile: `~/.claude/agent-memory/agent-builder/agent_$ARGUMENTS.md`
4. Generic pattern files: `~/.claude/agent-memory/agent-builder/pattern_*.md`
5. Agent-builder memory index: `~/.claude/agent-memory/agent-builder/MEMORY.md`
6. Command files the agent uses (find triggers in agent definition)
7. Permission settings: `.claude/settings.json`

## Step 1 — Pattern audit

For each generic pattern in `~/.claude/agent-memory/agent-builder/pattern_*.md`:

| Pattern | Applies? | Current state | Gap |
|---------|----------|---------------|-----|
| sequential-chunk-reading | yes/no | how agent currently handles it | what's missing |
| lint-invocation-flailing | yes/no | ... | ... |

For each item in the agent's audit profile `## Recurring issues`:
- Status FIXED → verify the fix is still in place (grep for it)
- Status OPEN → flag as tuning target
- Status PARTIALLY FIXED → flag with what's left

## Step 2 — Generate tuning checklist

Produce a checklist organized by fix layer:

```
## $ARGUMENTS — Tuning Checklist

### Agent definition (.claude/agents/$ARGUMENTS.md)
- [ ] item — reason

### Command file(s)
- [ ] item in <file> — reason

### Agent memory (.claude/agent-memory/$ARGUMENTS/)
- [ ] item — reason

### Permissions (.claude/settings.json)
- [ ] item — reason

### Hooks
- [ ] item — reason
```

Each item is a concrete recipe: exact file, exact change, expected impact.
No prose advice. No "consider doing X." Every item is actionable in one edit.

**Priority: harden existing recipes over writing new ones.**
If a recipe exists but agents deviate from it → make the recipe impossible to deviate from (STOP gates, deny rules, tighter wording).
If a recipe exists but hits permission blocks → fix permissions, don't rewrite the recipe.
Only create new recipes when no recipe covers the gap at all.

## Step 3 — Present and apply

Present the checklist. Ask:
```
Apply all / Apply specific (e.g. 1,3,5) / Skip
```

Apply selected items. For each:
1. Make the edit
2. Mark the checklist item done
3. If the edit touches a command file recipe, verify the recipe is permission-safe (check settings.json patterns)

## Step 4 — Update audit memory

After applying:
1. Update `~/.claude/agent-memory/agent-builder/agent_$ARGUMENTS.md` — mark tuned issues as addressed
2. If a new generic pattern emerged, write it to `~/.claude/agent-memory/agent-builder/pattern_<slug>.md`
3. Update `~/.claude/agent-memory/agent-builder/MEMORY.md` index if new files created
