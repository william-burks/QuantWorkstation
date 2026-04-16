# Story — Champion Degradation Advisory Rule

## ID
QWS-1405

## Status
READY

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
- [ ] `qw monitor --audit-lineage` prints advisory for Champions matching all 3 conditions
- [ ] Advisory silent for Champions not matching (hypothesis not rejected, or trades ≥ 10, or OOS not pending)
- [ ] `--dry-run` produces identical advisory output, no graph writes
- [ ] `qw degrade <id> --reason lineage_rejected` stores `degrade_reason` on FormerChampion node
- [ ] No automatic graph writes from `--audit-lineage`
- [ ] `make verify` passes with no new violations

## Definition of Done
- [ ] `monitor.py` updated with `--audit-lineage`
- [ ] `degrade.py` updated with `--reason`
- [ ] Unit tests pass
- [ ] Story marked CLOSED
