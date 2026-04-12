# Story — Phantom champion ID from auto-promotion

## ID
QWS-0904

## Status
READY

## Type
code

## Blocked On
None

## Summary
Fix `qw record --bundle` auto-promotion to print the persisted Neo4j champion ID, not a pre-write computed hash.

## Problem

`qw record --bundle` auto-promotes a trial to Champion and prints:

```
OK: Champion promoted — id=d1aa95c91f26
```

When the researcher uses that ID in a follow-up call (`qw record --oos oos_fail --champion d1aa95c91f26`), it returns OK but targets the wrong node — the actual Champion in the graph has a different ID (`b2a6d9624968`). The printed ID was computed before the Neo4j write transaction completed and was never persisted.

Any subsequent `--oos`, `--monitor`, or `--branched-from` using the printed ID silently fails or targets nothing.

## Goal

After auto-promotion, the printed champion ID matches exactly what `qw query --name recent_champions` returns for that strategy. If the write fails, an error is printed — not an OK with a phantom ID.

## Design

The fix is a read-after-write: after the champion write transaction commits, query Neo4j for the Champion node by `strategy_id` and print the ID returned by the graph. Do not derive or compute the ID client-side before the write.

If the write succeeds but the read-back returns no node, treat as a write failure and print an error with non-zero exit.

## In Scope
- `qws_graph/research/graph/cli.py` — auto-promotion write path: suppress pre-write ID print; add read-back query after commit; print persisted ID
- `qws_graph/research/graph/store.py` — verify `promote_champion()` (or equivalent) returns the persisted node ID from Neo4j, not a computed value; update return contract if needed
- `qws_graph/tests/integration/test_cli_record_bundle.py` — assert printed champion ID equals ID returned by `store.get_recent_champions()` for same strategy

## Out of Scope
- Changing how champion IDs are generated in Neo4j
- Backfilling previously promoted champions with mismatched IDs
- OOS or monitor command fixes — those are downstream; this story only fixes the source phantom ID

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — suppress pre-write ID; read-back after commit; print persisted ID or error
- `qws_graph/research/graph/store.py` — confirm `promote_champion()` returns persisted Neo4j ID; fix if returning computed hash
- `qws_graph/tests/integration/test_cli_record_bundle.py` — E2E assert: printed ID == graph ID for promoted champion

## Acceptance Criteria
- [ ] `qw record --bundle <dir>` prints champion ID only after the Neo4j write transaction commits
- [ ] Printed champion ID matches the ID returned by `qw query --name recent_champions` for the same strategy
- [ ] If Neo4j write succeeds but read-back finds no node, command exits non-zero with an error message (no OK printed)
- [ ] If Neo4j write fails, command exits non-zero with an error message (no OK printed)
- [ ] E2E test: auto-promoted champion printed ID == graph ID for same strategy

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED
