Check status and readiness for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate and verify status
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Read full file.

If Status is not `TESTING`, stop:
- Report current status
- Report what must happen before verification (must be implemented first)

## Step 2 — Report
```
## $ARGUMENTS — Status Check

- Status: <current status>
- Story file: <path>
- Ready for verification: YES | NO
- Blocker (if NO): <reason>
```
