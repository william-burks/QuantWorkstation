Close the QuantWorkstation story identified by: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story `$ARGUMENTS` in `qws_graph/epics/`. Read full file.
Stop if Status ≠ `TESTING`.

## Step 2 — Verify all ACs checked
Scan Acceptance Criteria. Any `- [ ]` or `- [FAILED]` → stop, report which are unmet.
If story has `## Acceptance Test Plan`, verify all referenced ACs are `- [x]`.
All must be `- [x]` to proceed.

## Step 3 — Verify DoD
Scan Definition of Done. Any `- [ ]` → stop, report incomplete items.

## Step 4 — Update story file
1. `## Status` → `CLOSED`
2. Any remaining `- [ ]` in DoD → `- [x]`

## Step 5 — Move to closed/
```
git mv <current_path> <epic_dir>/closed/<filename>
```

## Step 6 — Update INDEX.md
In `qws_graph/epics/INDEX.md`: status → `CLOSED`, path → `closed/<filename>`.

## Step 7 — Update BACKLOG_ALIGNMENT.md
In `docs/BACKLOG_ALIGNMENT.md`: mark CLOSED. Check if other stories list `$ARGUMENTS` in "Blocked On" — update those rows.

## Step 8 — Update CLAUDE.md
In `.claude/CLAUDE.md`: update sprint pointer to next unblocked story.

## Step 9 — Stage and commit
```
git add <story_new_path> qws_graph/epics/INDEX.md docs/BACKLOG_ALIGNMENT.md .claude/CLAUDE.md
git commit -m "close($ARGUMENTS): <one-line summary>"
```

## Step 10 — Report
```
## $ARGUMENTS — CLOSED

### Delivered
[capabilities now live]

### Unblocked
[stories that were blocked on this]

### Next
[next unblocked story]
```