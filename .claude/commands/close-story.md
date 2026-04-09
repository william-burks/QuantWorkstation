Close the QuantWorkstation story identified by: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate and verify status
Find the story file in `qws_graph/epics/` containing ID `$ARGUMENTS`.
Read the full story file.

If Status is not `TESTING`, stop and report:
- Current status
- What must happen before this story can be closed

## Step 2 — Verify all Acceptance Criteria are checked
Scan the Acceptance Criteria section. If any `- [ ]` remain unchecked, stop and report
which criteria are unmet. Do not proceed until all are `- [x]`.

## Step 3 — Verify Definition of Done
Scan the Definition of Done section. If any `- [ ]` remain unchecked, stop and report
which items are incomplete.

## Step 4 — Update story file
In the story file:
1. Change `## Status` to `CLOSED`
2. Change any remaining `- [ ]` in Definition of Done to `- [x]`

## Step 5 — Move to closed/
Determine the epic directory from the story's current path.
Move the story file to the `closed/` subdirectory of that epic:
```
git mv <current_path> <epic_dir>/closed/<filename>
```

## Step 6 — Update INDEX.md
In `qws_graph/epics/INDEX.md`:
1. Find the story entry for `$ARGUMENTS`
2. Change its status from `draft` / `ready` / `TESTING` to `CLOSED`
3. Update the file path to include `closed/` in the link

## Step 7 — Update BACKLOG_ALIGNMENT.md
In `docs/BACKLOG_ALIGNMENT.md`:
1. Find the story row for `$ARGUMENTS` in the Story → Capability Map
2. Note it as CLOSED
3. Check if any other stories list `$ARGUMENTS` in their "Blocked On" column —
   if so, update those rows to reflect the block is now resolved

## Step 8 — Update CLAUDE.md sprint pointer
In `.claude/CLAUDE.md`, update the **Current sprint** line to reflect the next
unblocked story based on `docs/BACKLOG_ALIGNMENT.md`.

## Step 9 — Stage and commit
```
git add <story_file_new_path>
git add qws_graph/epics/INDEX.md
git add docs/BACKLOG_ALIGNMENT.md
git add .claude/CLAUDE.md
```

Then commit:
```
git commit -m "close(QWS-XXXX): <one-line summary of what the story delivered>"
```

## Step 10 — Report
```
## $ARGUMENTS — CLOSED

### Delivered
[bullet list of capabilities now live]

### Unblocked
[any stories that were blocked on this one, now unblocked]

### Next
[next unblocked story in the sprint sequence]
```