# Story 1 — FormerChampion Lifecycle

## ID
QWS-0801

## Status
draft

## Blocked On
QWS-0402 (OOS outcome tracking must be CLOSED — `oos_fail` recording is the primary
trigger for Champion degradation)

## Summary
Introduce `FormerChampion` as a first-class node type, sitting between Champion and
RetiredChampion in the lifecycle. Add `DEGRADED_TO` and `RETIRED_TO` edges, mandatory
cause-of-death properties, and a `former_champions` MCP query preset — the "cemetery view"
that lets an LLM check whether a proposed strategy is a reskin of a dead edge.

## Problem
The current champion model is binary: active (Champion) or displaced (RetiredChampion).
When a Champion fails OOS, it is immediately archived with no structured reason recorded
and no intermediate state for "under watch." This creates two failures:

1. **No cause-of-death.** The `former_champions` tool listed in PROVENANCE_ENGINE.md is
   supposed to surface `oos_reason` and `retirement_note` — but those properties don't
   exist. Without cause-of-death, an LLM cannot reason about whether a proposed strategy
   avoids the original failure mode.

2. **No decay watch.** A Champion that is degrading slowly — Sharpe dropping, drawdown
   expanding — has no intermediate state. It stays "active" until manually retired.
   FormerChampion is that watch state: monitored, not yet archived.

## Goal
```zsh
# Manual demotion: Champion → FormerChampion
qw degrade <champion_id> --reason "MaxDD breached -15% in Oct CPI spike; OOS fail"

# Manual retirement: FormerChampion → RetiredChampion
qw retire <former_champion_id> --note "No pivot hypothesis; logic dead-ended"

# Cemetery view
qw query --name former_champions
```

The `former_champions` preset returns: `strategy_id`, `instrument`, `degraded_at`,
`oos_reason`, `retirement_note` (null if still in FormerChampion state), `status`
(`DEGRADED` | `RETIRED`).

## Schema

### `:FormerChampion` node
| Property | Type | Required | Description |
|---|---|---|---|
| `former_champion_id` | str | yes | `hash12(champion_id + degraded_at_iso)` |
| `strategy_id` | str | yes | Parent strategy |
| `champion_id` | str | yes | Source Champion node ID |
| `degraded_at` | datetime | yes | Timestamp of demotion |
| `oos_reason` | str | yes | Cause-of-death (mandatory — cannot be empty) |
| `metrics_sharpe_at_degradation` | float | no | Sharpe at time of demotion, if available |

### New edges
| Edge | Source → Target | Properties |
|---|---|---|
| `DEGRADED_TO` | Champion → FormerChampion | `detected_at: datetime` |
| `RETIRED_TO` | FormerChampion → RetiredChampion | `retired_at: datetime` |

### New properties on `:RetiredChampion`
| Property | Type | Description |
|---|---|---|
| `retirement_note` | str | Free-text reason for final retirement (set at `qw retire` time) |

### oos_reason enforcement
`qw degrade` requires `--reason` and rejects empty strings. The LLM instruction in
PROVENANCE_ENGINE.md is explicit: without cause-of-death, the cemetery view is useless.

## In Scope
- `qws_graph/research/graph/models.py` — `FormerChampionNode` Pydantic model
- `qws_graph/research/graph/store.py` — `degrade_champion()` and `retire_former_champion()`
  methods; DEGRADED_TO and RETIRED_TO edge creation; `retirement_note` property on
  RetiredChampion
- `qws_graph/research/graph/cli.py` — `qw degrade` and `qw retire` subcommands
- `qws_graph/research/graph/query_presets.py` — `former_champions` preset
- `qws_graph/docs/data_dictionary.yaml` — FormerChampion node, new edges, new properties
- `qws_graph/docs/graph_v1_contract.md` — add FormerChampion to schema section
- Unit tests for store methods, CLI flag parsing, oos_reason enforcement

## Out of Scope
- Automatic demotion at OOS fail (the `qw record --oos oos_fail` command surfaces a
  suggestion; Will runs `qw degrade` manually)
- Backfilling existing RetiredChampion nodes with `retirement_note`
- Decay threshold computation (that is QWS-0803)
- `BRANCHED_FROM` edge from new Hypothesis to FormerChampion (that is QWS-0601 scope)

## Repo Touchpoints
- `qws_graph/research/graph/models.py`
- `qws_graph/research/graph/store.py`
- `qws_graph/research/graph/cli.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_store_former_champion.py` — new
- `qws_graph/tests/unit/test_qw_degrade_retire.py` — new

## Acceptance Criteria
- [ ] `qw degrade <champion_id> --reason "..."` creates a FormerChampion node,
  creates a `DEGRADED_TO` edge from the Champion, and exits `0`.
- [ ] `qw degrade <champion_id>` without `--reason` exits non-zero with a clear error.
- [ ] `qw degrade <champion_id> --reason ""` (empty string) exits non-zero.
- [ ] `qw degrade <non_existent_id> --reason "..."` exits non-zero with a clear error.
- [ ] `qw retire <former_champion_id> --note "..."` creates a `RETIRED_TO` edge to the
  RetiredChampion and stores `retirement_note` on the RetiredChampion node.
- [ ] `qw retire <former_champion_id>` without `--note` succeeds (note is optional for retirement).
- [ ] `qw query --name former_champions` returns one row per FormerChampion with
  `strategy_id`, `instrument`, `degraded_at`, `oos_reason`, `retirement_note` (null if
  not yet retired), `status` (`DEGRADED` or `RETIRED`).
- [ ] The Champion node remains readable after demotion (not deleted).
- [ ] Unit tests cover: valid degrade, missing reason, empty reason, non-existent id,
  valid retire, retire without note, cemetery view query.

## Definition of Done
- [ ] FormerChampion node, DEGRADED_TO, RETIRED_TO edges implemented and tested.
- [ ] `qw degrade` and `qw retire` CLI commands operational.
- [ ] `former_champions` preset returns cemetery view.
- [ ] `data_dictionary.yaml` and `graph_v1_contract.md` updated.
- [ ] Story marked CLOSED — unblocks QWS-0803.
- [ ] All affected README files updated to reflect new capabilities.
- [ ] PROVENANCE_ENGINE.md updated — FormerChampion, DEGRADED_TO, RETIRED_TO, oos_reason,
  retirement_note moved from `[TARGET]` to `[CURRENT]`; former_champions tool updated.