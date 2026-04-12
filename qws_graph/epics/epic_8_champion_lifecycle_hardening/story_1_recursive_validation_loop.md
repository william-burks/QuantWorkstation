# Story 3 — Recursive Validation Loop

## ID
QWS-0803

## Status
TESTING

## Blocked On
~~QWS-0801 CLOSED~~ (satisfied)

## Summary
Add a `monitor_champion` scheduled skill that re-runs each active Champion's trial with
fresh data, computes Sharpe drift vs. the promotion baseline, and creates a `DEGRADED_TO`
edge when drift exceeds the decay threshold. Notifies Will and waits for direction.

## Problem
Champion decay goes undetected until Will manually runs a new trial or inspects OOS
results. A strategy can be silently degrading — Sharpe dropping from 2.8 to 1.7 across
three months — while still listed as "active" in the graph. There is no automatic signal.

The result: Will invests research time in directions downstream of a degraded Champion,
unaware the foundation has shifted.

## Goal
A scheduled skill (`monitor_champion`) runs on a configurable interval (default: weekly).
For each active Champion:

1. Re-runs the Champion's source trial script with a fresh date window.
2. Computes `sharpe_drift = abs(new_trial.sharpe - champion.metrics_sharpe)`.
3. If `sharpe_drift > decay_threshold` (default: 0.75):
   - Calls `store.degrade_champion()` to create a FormerChampion and DEGRADED_TO edge.
   - Emits a notification: "Strategy X hit decay threshold (drift=Y). Moved to FormerChampion.
     Run `qw query --name former_champions` for context. Options: pivot or retire."
4. If drift is within threshold: logs result silently to the graph (no notification).

Will's response is manual: either `qw degrade --reason` + new Hypothesis (`BRANCHED_FROM`)
for a pivot, or `qw retire` to archive.

## Schema Extension

### HAS_BLOB edge — source expansion
| Edge | Source → Target | Properties | Change |
|---|---|---|---|
| `HAS_BLOB` | FormerChampion → BlobArtifact | none | New source type; existing Strategy→BlobArtifact unaffected |

BlobArtifact node properties are unchanged. The notification content stored as BlobArtifact
should include: `artifact_type = "monitor_notification"`, `content = <notification text>`,
`created_at = datetime()`.

## Design

### Skill interface
```zsh
# Run manually
qw monitor

# Scheduled (via system cron or claude-code schedule skill)
# Default: weekly
```

### Decay threshold configuration
`decay_threshold` is read from the `ResearchTarget` node property `decay_threshold` (added
by this story); falls back to `0.75` when ResearchTarget is absent or property is unset.

### Auto-generated oos_reason
When monitor auto-creates a FormerChampion, it passes the following oos_reason to
`store.degrade_champion()`:
```
"Auto-detected by qw monitor on {date}: Sharpe drifted from {old_sharpe:.2f} to {new_sharpe:.2f} (drift={drift:.2f}, threshold={threshold:.2f})"
```

### Trial re-run mechanism
The monitor reads each Champion's `artifact_path` to identify the trial script, then
invokes it with a fresh date window (last `N` days, configurable). The script must be
shell-runnable without interactive input. Strategies without a runnable script path are
skipped with a warning.

This re-use of the existing trial runner avoids a new execution framework.

### Notification
Notification is written to stdout and also recorded as a `BlobArtifact` attached to the
FormerChampion node (`HAS_BLOB` edge), so the notification survives session boundaries
and is queryable.

## In Scope
- `qws_graph/research/graph/monitor.py` — new module: `MonitorRunner` class implementing
  the decay detection loop
- `qws_graph/research/graph/cli.py` — `qw monitor` subcommand; optional `--champion-id`
  to restrict to one Champion; `--dry-run` to report drift without writing edges
- `qws_graph/docs/data_dictionary.yaml` — document `decay_threshold` and monitor behavior;
  extend `HAS_BLOB` edge to also accept FormerChampion as source (FormerChampion → BlobArtifact);
  add `decay_threshold` property to ResearchTarget node (float, default 0.75, description:
  'Sharpe drift threshold for monitor_champion decay detection')
- Unit tests: drift above threshold triggers degrade; drift below threshold skips;
  dry-run produces no graph writes
- Integration test: end-to-end with a mock trial script that returns known Sharpe values

## Out of Scope
- Autonomous schedule setup (the schedule is configured externally via cron or Claude
  Code's schedule skill — this story provides the runnable command only)
- Automatic RETIRED_TO creation (Will decides whether to retire or pivot)
- Re-running trials that require live broker connections
- Strategies where the trial script path is unresolvable (skip with warning, do not fail)

## Repo Touchpoints
- `qws_graph/research/graph/monitor.py` — new
- `qws_graph/research/graph/cli.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/tests/unit/test_monitor.py` — new
- `qws_graph/tests/integration/test_monitor_end_to_end.py` — new

## Acceptance Criteria
- [x] `qw monitor --dry-run` reports Sharpe drift for all active Champions without
  writing any graph edges.
- [x] `qw monitor` creates a `DEGRADED_TO` edge and FormerChampion node when
  `sharpe_drift > decay_threshold` for any active Champion.
- [x] `qw monitor` does NOT create a `DEGRADED_TO` edge when drift is within threshold.
- [x] `qw monitor --champion-id <id>` runs the check for exactly one Champion.
- [x] Notification message includes: strategy_id, instrument, old Sharpe, new Sharpe,
  drift value, and the two manual follow-up options (pivot or retire).
- [x] Notification is stored as a `BlobArtifact` attached to the FormerChampion node.
- [x] A Champion with an unresolvable trial script path is skipped with a logged warning;
  other Champions continue to be evaluated.
- [x] `decay_threshold` defaults to `0.75` when `ResearchTarget` node is absent or
  `decay_threshold` property is unset.
- [x] FormerChampion created by `qw monitor` has `oos_reason` set to the auto-generated
  monitor format string (includes old Sharpe, new Sharpe, drift value, threshold).
- [x] Unit tests cover: above-threshold, below-threshold, dry-run, single-champion scope,
  missing script path.

## Definition of Done
- [x] `monitor.py` module implemented and tested.
- [x] `qw monitor` CLI subcommand operational with `--dry-run` and `--champion-id` flags.
- [x] Notification written to stdout and stored as BlobArtifact.
- [x] Integration test passes with mock trial runner.
- [x] `data_dictionary.yaml` updated.
- [ ] Story marked CLOSED.
- [x] All affected README files updated to reflect new capabilities.
- [x] PROVENANCE_ENGINE.md updated — monitor_champion tool moved from `[TARGET]` to
  `[CURRENT]`; Recursive Validation Loop section updated to reflect actual implementation.

## Acceptance Test Plan

### AC1: dry-run reports drift without writing edges
- type: cli
- cmd: `qw monitor --dry-run`
- expect_contains: "DRY-RUN"
- expect_exit: 0

### AC2: degradation creates DEGRADED_TO edge on drift > threshold
- type: regression
- cmd: unit test `TestEvaluateChampionAboveThreshold::test_creates_former_champion_when_above_threshold`
- expect_contains: status=="degraded", former_champion_id set, degrade_champion called once
- expect_exit: 0 (pytest)

### AC3: no DEGRADED_TO edge when drift within threshold
- type: regression
- cmd: unit test `TestEvaluateChampionBelowThreshold::test_no_degrade_when_below_threshold`
- expect_contains: status=="ok", degrade_champion not called
- expect_exit: 0 (pytest)

### AC4: --champion-id restricts to one champion
- type: regression
- cmd: unit test `TestSingleChampionScope::test_run_with_champion_id_filters_to_one`
- expect_contains: len(results)==1, champion_id=="c1"
- expect_exit: 0 (pytest)

### AC5: notification includes strategy_id, drift, pivot/retire options
- type: regression
- cmd: unit test `TestEvaluateChampionAboveThreshold::test_notification_includes_strategy_id`
- expect_contains: strategy_id in content, "pivot or retire" in content
- expect_exit: 0 (pytest)

### AC6: notification stored as BlobArtifact on FormerChampion
- type: regression
- cmd: integration test `TestMonitorEndToEnd::test_above_threshold_creates_degrade`
- expect_contains: attach_blob_to_former_champion called with artifact_type="monitor_notification"
- expect_exit: 0 (pytest)

### AC7: unresolvable script path skipped, others continue
- type: regression
- cmd: unit test `TestMissingScript::test_other_champions_continue_after_skip`
- expect_contains: statuses["c1"]=="skipped", statuses["c2"] in valid set
- expect_exit: 0 (pytest)

### AC8: decay_threshold falls back to 0.75
- type: regression
- cmd: unit test `TestResolveThreshold::test_falls_back_to_default_when_no_target`
- expect_contains: threshold==0.75
- expect_exit: 0 (pytest)

### AC9: oos_reason format string correct
- type: regression
- cmd: unit test `TestEvaluateChampionAboveThreshold::test_oos_reason_format`
- expect_contains: "Auto-detected by qw monitor", old/new sharpe values, drift, threshold
- expect_exit: 0 (pytest)

### AC10: unit tests cover all required cases
- type: regression
- cmd: `pytest qws_graph/tests/unit/test_monitor.py -v`
- expect_contains: 29 passed
- expect_exit: 0