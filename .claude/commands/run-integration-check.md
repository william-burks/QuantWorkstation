Run integration tests for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Note code paths touched.

## Step 2 — Find relevant integration tests
Check `qws_graph/tests/integration/`. Identify tests that cover code paths touched by this story.

If no relevant tests found — report "No integration tests cover this story's code paths" and stop.

## Step 3 — Run (if applicable)
```
pytest qws_graph/tests/integration/ -v -k "<relevant test names>" 2>&1
```
Integration tests require live Neo4j. If Neo4j unreachable:
- Note "integration tests skipped — Neo4j not available"
- List tests that would have run

## Step 4 — Report
```
## $ARGUMENTS — Integration Check Report

### Tests identified
- <test name>: <what it covers>

### Result
- Passed: X | Failed: Y | Skipped: Z
- Skip reason (if any): <reason>

### Failures (if any)
- <test>: <diagnosis>
```
