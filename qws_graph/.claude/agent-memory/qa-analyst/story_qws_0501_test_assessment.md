---
name: QWS-0501 Test Assessment
description: Detailed testing coverage audit for family_id population story (QWS-0501)
type: reference
---

# QWS-0501 Test Coverage Assessment

**Story ID:** QWS-0501
**Status:** TESTING
**Acceptance Criteria:** 3 items (1 checked, 2 unchecked)
**Definition of Done:** 3 items (0 checked)

## What the Story Actually Does

Story was meant to update "four production runners" to pass `--source-file` flag to `qw record` so family_id is populated on Strategy nodes. However:

- **Actual runners found:** 2 (not 4)
  - `research/bin/run_liquidity_sweep.sh` (parameterized, covers baseline/position_sizing/golden)
  - `research/bin/run_btc_mars_golden.sh`
  
- **Other runners with record_artifact:**
  - `research/bin/run_es_nq_bear_sweep_1h_baseline.sh` (has --source-file in calls)
  - `research/bin/run_es_phase2.sh` (does NOT have --source-file, but marked out-of-scope in story)

- **Infrastructure:** `research/bin/_qws_env.sh` has `record_artifact()` helper that already supports --source-file parameter (line 33)

## Runners Already Updated with --source-file

1. **run_btc_mars_golden.sh:32** — `qw record --bundle "$CSV_DIR" --source-file "research/trials/crypto/mars/golden.py"`
2. **run_liquidity_sweep.sh:29** — `qw record --bundle "${RUN_DIR}" --source-file "${TRIAL_SCRIPT}"`
3. **run_liquidity_sweep.sh:32** — `qw record --file "$md" --kind "champion_md" --source-file "${TRIAL_SCRIPT}"`
4. **run_es_nq_bear_sweep_1h_baseline.sh:17** — `record_artifact "results/es_bear_sweep_1h_baseline.csv" "baseline_csv" "strategies/legacy/bear_es_sweep_1h_baseline.py"`
5. **run_es_nq_bear_sweep_1h_baseline.sh:22** — `record_artifact "results/nq_bear_sweep_1h_baseline.csv" "baseline_csv" "strategies/legacy/bear_nq_sweep_1h_baseline.py"`

## Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | All four production runners pass `--source-file` to `qw record` | CHECKED (✓) | run_btc_mars_golden.sh:32, run_liquidity_sweep.sh:29/32, run_es_nq_bear_sweep_1h_baseline.sh:17/22 — **BUT story says "four runners" when really using 2 main runners + parameterization** |
| 2 | After fresh pipeline run, `MATCH (s:Strategy) WHERE s.family_id IS NULL` returns 0 | UNCHECKED | Requires live Neo4j execution; no unit test covers this |
| 3 | `qw query --name cross_artifact_correlation` returns non-empty results | UNCHECKED | Requires live Neo4j execution; no unit test covers this |

## Test Coverage

### Unit Tests Present

**File:** `tests/unit/test_bundle.py`

- **test_source_file_attaches_family_id_on_bundle** (lines 138-194)
  - Tests: `_cmd_bundle()` with `--source-file` flag
  - Verifies: `family_id` is non-None when source file provided
  - Coverage: Positive path only (source file present)
  
- **test_bundle_without_source_file_leaves_family_id_none** (lines 196-246)
  - Tests: `_cmd_bundle()` WITHOUT `--source-file` flag
  - Verifies: `family_id` remains None when source file omitted
  - Coverage: Negative path (absence of source file)

**File:** `tests/unit/test_ids.py` (lines 27-94)

- **TestSourceHash** (4 tests)
  - source_hash returns 12-char hex
  - source_hash is deterministic
  - Different content → different hash
  - Empty bytes produces valid hash
  
- **TestFamilyId** (8 tests)
  - family_id returns 12-char hex
  - family_id is deterministic
  - Same logic/direction with same source → same family_id across instruments
  - Different logic_type → different family_id
  - Different direction → different family_id
  - Different source_hash → different family_id
  - family_id independent of filename/path
  - Normalizes logic_type and direction case

### CLI Implementation (research/graph/cli.py)

**cmd_record()** (lines 671-686)
- Reads source_file from args
- Calls source_hash() and family_id() 
- Attaches family_id to strategy before persist
- ✓ Present and correct

**_cmd_bundle()** (lines 334-351)
- Reads source_file from args
- Calls source_hash() and family_id()
- Attaches family_id to strategy before persist
- ✓ Present and correct

## Gaps and Missing Tests

### Test Gaps

1. **Integration test for cmd_record with --source-file NOT present**
   - `tests/integration/test_cli_record_reconcile.py` has no test for --source-file on record
   - No dry-run or offline mode test verifying family_id computation
   
2. **Integration test for --source-file file reading errors**
   - Unit tests assume happy path (file readable)
   - No test for OSError when source_file unreadable
   
3. **Integration test verifying Neo4j persistence**
   - Unit tests mock the persist call
   - No test confirms family_id actually written to Strategy node in graph
   - No test confirms `MATCH (s:Strategy) WHERE s.family_id IS NULL` returns appropriate count

4. **Query preset test**
   - No test verifies `cross_artifact_correlation` query returns results when strategies share family_id
   - Preset catalog may exist but not tested with populated family_id

5. **E2E test for runner scripts**
   - No test runs the actual shell runners to verify --source-file is passed correctly
   - No test confirms bundle.json is created correctly

### Missing Properties/Fixtures

1. **Demo graph seed** (`research/graph/store.py` seed_demo_graph)
   - May already populate demo strategies with family_id (line 97 in docs mentions `demo-strategy-alpha` and `demo-strategy-beta` share family_id)
   - Need to verify fixture creates both with matching family_id

2. **Strategy fixture** (`tests/fixtures/strategies/strategy_source_fixture.py`)
   - ✓ Present and adequate (has logic_type, direction for testing)
   - Used by unit tests to read actual file content for realistic hashing

## Definition of Done Checkpoints

| Item | Status | Notes |
|------|--------|-------|
| Four runners updated | DONE (4/4 actual) | BUT runner count/names don't match story description |
| Neo4j spot-check for family_id | NOT VERIFIED | Requires manual `MATCH (s:Strategy) RETURN s.family_id` query |
| Story marked CLOSED | NOT DONE | Status is still TESTING; depends on manual verification above |

## Commands Will Should Run

### Unit Tests (all pass)
```bash
pytest tests/unit/test_bundle.py::TestCmdBundleErrors::test_source_file_attaches_family_id_on_bundle -v
pytest tests/unit/test_bundle.py::TestCmdBundleErrors::test_bundle_without_source_file_leaves_family_id_none -v
pytest tests/unit/test_ids.py::TestSourceHash -v
pytest tests/unit/test_ids.py::TestFamilyId -v
```

### Integration Tests (may need live Neo4j)
```bash
pytest tests/integration/test_cli_record_reconcile.py -v -k "record"
```

### Manual Neo4j Verification (required for AC #2 and #3)
```cypher
# After running one of the updated runners:
MATCH (s:Strategy) WHERE s.family_id IS NULL RETURN count(s);  # Should return 0

MATCH (s:Strategy) WHERE s.family_id IS NOT NULL RETURN s.strategy_id, s.family_id LIMIT 10;

qw query --name cross_artifact_correlation --param strategy_id=cl-1h-bear-liquidity-sweep
```

### Demo Graph Verification
```bash
qw seed --demo
qw query --name cross_artifact_correlation --param strategy_id=demo-strategy-alpha
# Should return non-empty (if both demo-strategy-alpha and demo-strategy-beta share family_id)
```

## Risk Areas

1. **Story description mismatch with implementation**
   - Story mentions "four separate runners" but actual codebase uses parameterized runners
   - AC #1 marked complete but uncertainty whether this is accurate vs aspirational
   
2. **AC #2 and #3 untested at unit level**
   - Both require live Neo4j
   - No integration test ensures runner scripts actually pass --source-file correctly
   
3. **Cross-artifact queries depend on schema**
   - cross_artifact_correlation preset must use family_id correctly
   - If query doesn't exist or is broken, AC #3 will fail regardless of family_id being set
   
4. **Demo seed may be stale**
   - Docs mention demo-strategy-alpha/beta share family_id
   - If seed_demo_graph() wasn't updated with this requirement, demo won't work as documented
