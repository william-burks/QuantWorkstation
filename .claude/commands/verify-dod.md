Cross-check Definition of Done and update story file for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Read full file.

## Step 2 — Evaluate each DoD item
Re-read story's Definition of Done section. For each item, classify:

**Auto-verifiable** (pytest, ruff, mypy):
- Run if not already run this session
- Check off if clean

**Requires Will's environment** (live Neo4j, manual CLI walk, live data):
- Flag explicitly with exact command Will must run and expected output
- Leave unchecked

## Step 3 — Run any outstanding automatable checks
If ruff/mypy not yet run on files touched by this story:
```
ruff check <files> && mypy --strict <files> 2>&1
```

## Step 4 — Update DoD checkboxes in story file
Check off every DoD item verified automatically.
Leave unchecked only items requiring Will's manual verification.

## Step 5 — Stage story file
```
git add <story file path>
```

## Step 6 — Report
```
## $ARGUMENTS — DoD Verification Report

### DoD items verified automatically
- [x] <item>

### DoD items requiring Will's manual verification
- [ ] <item>
  - Command: `<exact command>`
  - Expected: <what passing looks like>

### Remaining before CLOSED
<list anything still blocking close; "None — ready to close" if all clear>
```