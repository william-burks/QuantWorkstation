# Epic 8 — Champion Lifecycle

## Objective
Extend the champion model from binary (active / retired) to three-stage (active →
FormerChampion → RetiredChampion), add a direct link when one Champion replaces another,
and automate decay detection with a scheduled validation loop.

## Why it exists
After Epic 4, Champions can record OOS outcomes and surface promotion candidates. But the
model still has no structured decay path. A Champion that fails OOS is immediately retired
with no intermediate watch state and no queryable cause-of-death. As a result:

1. There is no "cemetery view" — the LLM cannot query which strategies degraded and why,
   which means the same dead edges get re-proposed.
2. When a Champion is replaced by a better version, there is no direct link from old to new.
   Lineage is only traversable via the Strategy node (two hops), not directly.
3. Decay goes undetected until Will manually runs a fresh trial. There is no automated
   signal when a Champion's live performance has drifted from its promotion baseline.

These three stories address one coherent concern: the full lifecycle of a Champion node
from peak performance through decay, replacement, or retirement.

## What this epic is NOT
- Not a monitoring dashboard. The output is graph edges and CLI notifications, not UI.
- Not an autonomous trading decision. Will approves every DEGRADED_TO and RETIRED_TO action.
  The system surfaces evidence; Will decides.
- Not a backfill. Existing Champions and RetiredChampions are not retroactively labelled.
  The new lifecycle applies to transitions that occur after this epic is implemented.

## Scope
- `FormerChampion` node as the intermediate decay state.
- `DEGRADED_TO` edge (Champion → FormerChampion) and `RETIRED_TO` edge
  (FormerChampion → RetiredChampion).
- `oos_reason` and `retirement_note` properties on FormerChampion / RetiredChampion.
- `former_champions` MCP query preset (the "cemetery view").
- `SUPERSEDED_BY` edge (Champion → Champion v2) created at promotion time.
- `monitor_champion` scheduled skill that detects decay and creates `DEGRADED_TO`
  edges when drift exceeds threshold.

## Stories in execution order
1. `QWS-0801` `story_1_former_champion_lifecycle.md` — FormerChampion node, DEGRADED_TO /
   RETIRED_TO edges, oos_reason / retirement_note properties, former_champions preset,
   qw degrade / qw retire CLI commands
2. `QWS-0802` `story_2_superseded_by_relationship.md` — SUPERSEDED_BY edge created at
   promotion time (independent of QWS-0801)
3. `QWS-0803` `story_3_recursive_validation_loop.md` — monitor_champion scheduled skill
   (blocked on QWS-0801)

Stories 1 and 2 are independent of each other. Story 3 requires Story 1 to be CLOSED.

## Dependencies
- QWS-0402 (OOS outcome tracking) must be CLOSED before QWS-0801, as FormerChampion
  lifecycle is triggered by `oos_fail` outcomes recorded there.
- Epic 4 otherwise complete.
- No Epic 5 or Epic 6 dependency.

## Exit Criteria
- `qw degrade <champion_id> --reason <text>` moves a Champion to FormerChampion.
- `qw retire <former_champion_id> --note <text>` archives a FormerChampion.
- `qw query --name former_champions` returns the cemetery view with cause-of-death.
- A new Champion promotion creates a `SUPERSEDED_BY` edge from the displaced Champion
  to the new one, queryable before the displaced Champion becomes a RetiredChampion.
- `monitor_champion` re-runs each active Champion's trial on fresh data and auto-creates
  `DEGRADED_TO` when decay threshold is breached, with a notification to Will.