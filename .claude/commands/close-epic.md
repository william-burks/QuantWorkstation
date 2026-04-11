Close QuantWorkstation epic: $ARGUMENTS

## Step 1 — Verify all stories CLOSED
Read `qws_graph/epics/INDEX.md`. Find all stories for epic $ARGUMENTS.
If ANY story is not `CLOSED` → STOP. Report outstanding stories.

## Step 2 — Rename epic directory
```
git mv qws_graph/epics/<epic_dir> qws_graph/epics/<epic_dir>[COMPLETE]
```

## Step 3 — Update INDEX.md
1. Change epic status from `PLANNED` → `COMPLETE`
2. Update epic README path to include `[COMPLETE]` in directory name
3. Update all story file paths within the epic section to include `[COMPLETE]`

## Step 4 — Update BACKLOG_ALIGNMENT.md
In `docs/BACKLOG_ALIGNMENT.md`:
1. Mark epic as `COMPLETE` in the Epic Status table
2. Check if any stories in other epics were blocked on this epic — update their rows

## Step 5 — Update CLAUDE.md
In `.claude/CLAUDE.md`: update sprint pointer to next active epic and its first unblocked story.

## Step 6 — Stage and commit
```
git add qws_graph/epics/INDEX.md docs/BACKLOG_ALIGNMENT.md .claude/CLAUDE.md
git commit -m "close(epic-$ARGUMENTS): <epic name> — all stories CLOSED"
```

## Step 7 — Report
```
## Epic $ARGUMENTS — COMPLETE

### Stories closed
[list]

### Capabilities delivered
[bullet list of what this epic built]

### Unblocked
[epics or stories that were waiting on this]

### Next
[next active epic and first unblocked story]
```
