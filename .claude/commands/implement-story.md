Implement the QuantWorkstation story identified by: $ARGUMENTS

## Step 1 — Locate and read the story
Search `qws_graph/epics/` for a story file containing the ID `$ARGUMENTS`.
Read the full story file. If Status is not `draft` or `ready`, stop and report why.

## Step 2 — Verify unblocked
Read `docs/BACKLOG_ALIGNMENT.md`. Check the "Blocked On" column for this story.
If blocked, stop and report exactly what must be completed first.

## Step 3 — Read context
Read these files before writing any code:
- The story's "Repo Touchpoints" section — read every file listed
- `docs/PROVENANCE_ENGINE.md` — schema and MCP tool reference
- `docs/BACKLOG_ALIGNMENT.md` — confirm this story's capabilities are not marked [TARGET] elsewhere

Do NOT use any node types, relationships, or MCP tools marked [TARGET] in PROVENANCE_ENGINE.md
unless this story is explicitly the one implementing them.

## Step 4 — Implement
Work through the Acceptance Criteria one by one, in order.

After each criterion is satisfied:
1. Edit the story file: change `- [ ]` to `- [x]` for that criterion
2. Run `git add` on every file you edited or created (never use `git add -A` or `git add .`)
3. Confirm the criterion is met before moving to the next

Follow the existing code patterns in the repo. Run `pytest tests/unit/ -v` after touching
any Python file. Fix all failures before continuing to the next criterion.

## Step 5 — Update story status
Once all Acceptance Criteria are checked:
1. Change the story's `## Status` field from `READY` to `TESTING`
2. Change the story's `Status` from `READY` to `TESTING` in the epic README and docs/BACKLOG_ALIGNMENT.md
2. Run `git add` on the story file

## Step 6 — Report
Produce a structured testing report for Will:

```
## $ARGUMENTS — Ready for Testing

### What was implemented
[bullet list of changes, file by file]

### How to test (manual steps required from Will)
[numbered list of exact commands or actions Will needs to run]
[include expected output for each step]

### Automated tests
[confirm: pytest tests/unit/ -v passes — show result]

### Definition of Done remaining
[any DoD items that require Will's environment, live Neo4j, or manual verification]
```

Do not mark the story CLOSED. That is Will's decision after testing passes.
