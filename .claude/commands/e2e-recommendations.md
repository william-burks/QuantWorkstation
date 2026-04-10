Map Acceptance Criteria to e2e scenarios for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Read full file.
Note all Acceptance Criteria.

## Step 2 — Read e2e suite
Read `qws_graph/tests/e2e/run_e2e.py`. Note available scenarios and their names.

## Step 3 — Map AC to scenarios
For each Acceptance Criterion:
1. Identify which e2e scenario(s) cover it (if any)
2. If no scenario covers it — note gap

Do NOT execute e2e tests automatically. Output commands for Will to run manually.

## Step 4 — Report
```
## $ARGUMENTS — E2E Recommendations

### AC → Scenario mapping
| AC | Scenario | Command |
|----|----------|---------|
| <ac text> | <scenario name> | `python qws_graph/tests/e2e/run_e2e.py --scenario <name>` |
| <ac text> | NO COVERAGE | — |

### Gaps (ACs with no e2e coverage)
- <ac>: <suggested scenario name if worth adding>

### Commands to run
```
python qws_graph/tests/e2e/run_e2e.py --scenario <name1>
python qws_graph/tests/e2e/run_e2e.py --scenario <name2>
```
```