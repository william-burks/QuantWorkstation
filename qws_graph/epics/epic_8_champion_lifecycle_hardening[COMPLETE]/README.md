# Epic 8 — Champion Lifecycle Hardening

## Objective
Close two lifecycle gaps that remain after Epic 7: automated decay detection via a
scheduled validation loop, and a direct one-hop lineage edge when one Champion replaces
another.

## Why it exists
Epic 7 shipped the FormerChampion cemetery (QWS-0801 CLOSED). Two follow-on stories
unblock the full automated lifecycle:

1. `SUPERSEDED_BY` — when a Champion is displaced at promotion time, there is no direct
   edge from old to new. Lineage requires four hops through Strategy. One-hop lineage
   is missing.
2. Recursive Validation Loop — decay goes undetected until manual inspection. No automated
   signal when a live Champion's Sharpe has drifted from its promotion baseline.

Epic 8 completes the Champion lifecycle model. Epic 12 (ML Research Layer) has a hard gate:
QWS-0803 must CLOSE before any ML Champion can be promoted.

## Stories

| ID | Name | Status | Blocked On |
|---|---|---|---|
| QWS-0802 | SUPERSEDED_BY Relationship | READY | — |
| QWS-0803 | Recursive Validation Loop | READY | ~~QWS-0801 CLOSED~~ (satisfied) |
| QWS-0805 | Champion Promotion Rationale | READY | — |

Story files:
- `story_2_superseded_by_relationship.md`
- `story_1_recursive_validation_loop.md`
- `story_3_champion_promotion_rationale.md`

## Dependency Notes
- QWS-0802 is independent — implement first or in parallel with QWS-0803.
- QWS-0803 was blocked on QWS-0801 (FormerChampion node). QWS-0801 is now CLOSED — blocker satisfied.
- Epic 12 entry blocked on QWS-0803 CLOSED.
- Epic 10 (Macro Data) can proceed independently of Epic 8.

## Done Criteria
- `SUPERSEDED_BY` edge created atomically at promotion time (both store.py and cypher.py paths).
- `(RetiredChampion)-[:SUPERSEDED_BY]->(Champion)` traversable after relabeling.
- `qw monitor --dry-run` reports Sharpe drift for all active Champions without writing edges.
- `qw monitor` creates `DEGRADED_TO` edge and FormerChampion when `sharpe_drift > decay_threshold`.
- Notification written to stdout and stored as BlobArtifact attached to FormerChampion.
- `monitor_champion` MCP tool moves from `[TARGET]` to `[CURRENT]` in PROVENANCE_ENGINE.md.
- `SUPERSEDED_BY` moves from `[TARGET]` to `[CURRENT]` in PROVENANCE_ENGINE.md.
- Both story files marked CLOSED.
