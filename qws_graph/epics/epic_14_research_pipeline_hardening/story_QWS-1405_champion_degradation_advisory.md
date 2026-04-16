# Story — Champion Degradation Advisory Rule

## ID
QWS-1405

## Status
TESTING

## Type
code

## Blocked On
None (`qw monitor` and `qw degrade` both exist)

## Summary
Add `--audit-lineage` flag to `qw monitor`. Traverses `Champion -> PIVOTED_FROM -> Run <- HAS_RUN <- Strategy <- TESTED_AS <- Hypothesis`. Warns when hypothesis rejected AND champion has low trade count AND OOS is pending. Advisory only — no auto graph writes.

## Problem
A Champion can persist with a rejected source hypothesis and unverified OOS without any automated signal. Manual lineage audits are ad-hoc. No convenience path to degrade after confirming the advisory.

## Goal
After this story:
```bash
qw monitor --audit-lineage
# ADVISORY: Champion <id> — source hypothesis rejected, OOS pending, only 7 IS trades.
# Run `qw degrade <id> --reason lineage_rejected` to act on this.

qw monitor --audit-lineage --dry-run
# Same output, no graph writes (already true — advisory makes no writes)
```

## Design

### Traversal
```cypher
MATCH (c:Champion)-[:PIVOTED_FROM]->(r:Run)<-[:HAS_RUN]-(s:Strategy)<-[:TESTED_AS]-(h:Hypothesis)
WHERE h.status = 'rejected'
  AND c.metrics_total_trades < 10
  AND c.oos_status = 'oos_pending'
RETURN c, h
```

### Warning output
```
ADVISORY: Champion {c.id} ({c.name})
  Source hypothesis: {h.id} — status=rejected
  IS trades: {c.metrics_total_trades} | OOS: {c.oos_status}
  Action: qw degrade {c.id} --reason lineage_rejected
```

### `qw degrade --reason` flag
- Add `--reason` optional string to existing `qw degrade` command
- Stored as `degrade_reason` string on the FormerChampion node
- `degrade_reason` is now a declared optional property in `data_dictionary.yaml` and `PROVENANCE_ENGINE.md` (added by this story)
- If `--reason` omitted, behavior unchanged

### Invariants
- `--audit-lineage` makes NO graph writes
- `qw degrade` with `--reason` only writes `degrade_reason` to FormerChampion (existing promotion path unchanged)
- No auto-degrade trigger of any kind

## In Scope
- `qws_graph/cli/monitor.py` (or equivalent) — `--audit-lineage` flag + traversal + output
- `qws_graph/cli/degrade.py` (or equivalent) — `--reason` flag + FormerChampion write
- Unit tests: advisory fires for matching graph fixture, silent for non-matching, degrade --reason stored correctly

## Out of Scope
- Automatic degradation
- Threshold changes (10 trades, oos_pending are fixed)
- New node types or edge types
- Changes to existing Champion promotion flow

## Repo Touchpoints
- `qws_graph/cli/monitor.py` (verify exact path before edit)
- `qws_graph/cli/degrade.py` (verify exact path before edit)
- `tests/unit/test_champion_advisory.py` — new

## Acceptance Criteria
- [x] `qw monitor --audit-lineage` prints advisory for Champions matching all 3 conditions
- [x] Advisory silent for Champions not matching (hypothesis not rejected, or trades ≥ 10, or OOS not pending)
- [x] `--dry-run` produces identical advisory output, no graph writes
- [x] `qw degrade <id> --degrade-reason lineage_rejected` stores `degrade_reason` on FormerChampion node
- [x] No automatic graph writes from `--audit-lineage`
- [x] `make verify` passes with no new violations

## Definition of Done
- [x] `monitor.py` updated with `--audit-lineage`
- [x] `degrade.py` updated with `--reason`
- [x] Unit tests pass
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: Advisory fires for matching Champions
- type: cli
- cmd: `python -c "from unittest.mock import MagicMock, patch; ..."` (covered by unit test TestAuditLineage::test_advisory_fires_for_matching_champion)
- expect_contains: "ADVISORY:"
- expect_exit: 0

### AC2: Advisory silent for non-matching
- type: cli
- cmd: covered by TestAuditLineage::test_advisory_silent_for_empty_results
- expect_contains: "" (no output)
- expect_exit: 0

### AC3: --dry-run identical output, no graph writes
- type: regression
- cmd: covered by TestCmdMonitorAuditLineage::test_dry_run_with_audit_lineage_produces_same_output
- expect_contains: "ADVISORY:"
- expect_exit: 0

### AC4: --degrade-reason stored on FormerChampion
- type: cli
- cmd: covered by TestCmdDegradeReason::test_degrade_reason_passed_to_store
- expect_contains: store.degrade_champion called with degrade_reason="lineage_rejected"
- expect_exit: 0

### AC5: No auto graph writes from --audit-lineage
- type: regression
- cmd: covered by TestCmdMonitorAuditLineage::test_dry_run_with_audit_lineage_produces_same_output
- expect_contains: mock_store.degrade_champion.assert_not_called()
- expect_exit: 0

### AC6: make verify passes
- type: cli
- cmd: `make check-story`
- expect_contains: "Success: no issues found" and "passed"
- expect_exit: 0
