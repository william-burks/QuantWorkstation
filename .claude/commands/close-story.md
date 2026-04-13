Close the QuantWorkstation story identified by: $ARGUMENTS

## Allowed files
You may ONLY edit these files during close-story:
- The story file itself (`qws_graph/epics/.../$ARGUMENTS...`)
- `qws_graph/epics/INDEX.md`
- `docs/BACKLOG_ALIGNMENT.md`
- `docs/PROVENANCE_ENGINE.md`

**CLAUDE.md is NOT in scope.** Do not edit `.claude/CLAUDE.md`.

## Step 1 — Locate story
```bash
STORY_FILE=$(.claude/scripts/locate-story.sh $ARGUMENTS)
```
If exit 1 → report BLOCKED (story not found).
Read the file at `$STORY_FILE`. Stop if Status ≠ `TESTING`.

## Step 2 — Verify all ACs checked
Scan Acceptance Criteria. Any `- [ ]` or `- [FAILED]` → stop, report which are unmet.
If story has `## Acceptance Test Plan`, verify all referenced ACs are `- [x]`.
All must be `- [x]` to proceed.

## Step 3 — Verify DoD
Scan Definition of Done. Any `- [ ]` → stop, report incomplete items.

## Step 4 — Update story file
1. Set story status to `CLOSED` in story file, INDEX.md, and BACKLOG_ALIGNMENT.md in one call.
```bash
.claude/scripts/set-story-status.sh $ARGUMENTS CLOSED
```
2. Any remaining `- [ ]` in DoD → `- [x]` (Edit story file directly for DoD checkboxes)

**After this step: also check BACKLOG_ALIGNMENT.md for other stories listing `$ARGUMENTS` in "Blocked On" — add strikethrough `~~$ARGUMENTS~~` to those rows manually.**

## Step 5 — Move to closed/
```
git mv <current_path> <epic_dir>/closed/<filename>
```

## Step 6 — Update INDEX.md path
Status was already set in Step 4. Only the path needs updating:
In `qws_graph/epics/INDEX.md`: update path → `closed/<filename>`.

## Step 7 — Update BACKLOG_ALIGNMENT.md blocked-on rows
Status was already set in Step 4. Only the "Blocked On" strikethrough remains:
**Edit-planning rule:** Read full relevant range ONCE. List ALL changes. Execute. No re-reads.
Check if other stories list `$ARGUMENTS` in "Blocked On" — add `~~$ARGUMENTS~~` to those rows.

## Step 8 — Stage and commit
**This commit is explicitly requested by the close-story command. The CLAUDE.md "No auto-commit" rule does not apply here.**
```
make commit-close-story STORY=$ARGUMENTS MSG="close($ARGUMENTS): <one-line summary>"
```

## Step 9 — Report
```
## $ARGUMENTS — CLOSED

### Delivered
[capabilities now live]

### Unblocked
[stories that were blocked on this]

### Next
[next unblocked story]
```