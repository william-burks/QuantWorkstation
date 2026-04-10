# Story 0 — OOS Sharpe Amendment (QWS-0402C)

## ID
QWS-0402C

## Status
CLOSED

## Summary
Amend `qw record --oos` to accept an optional `--sharpe <float>` argument. Store
`metrics_oos_sharpe` on the Champion node at OOS record time. Unblocks IS/OOS drift
analysis in `compare_strategy_performance` (QWS-0503) and `portfolio_alpha` (QWS-0603).

## Problem
QWS-0402 added `oos_status` (pass/fail) and `oos_date` to Champion. It did not capture
the OOS Sharpe value. As a result:
- `compare_strategy_performance` (QWS-0503) has a null `oos_sharpe` column permanently
- IS/OOS drift fragility signal (PROVENANCE_ENGINE) cannot be computed
- `portfolio_alpha` correlation guard (QWS-0603) loses its primary drift input

OOS Sharpe is already known at the time `qw record --oos` is called — the researcher
has the result. This patch adds a one-argument extension to capture it.

## Fix
```zsh
# Current
qw record --oos pass --champion 2652b09c139f

# After patch
qw record --oos pass --champion 2652b09c139f --sharpe 3.21
```

`--sharpe` is optional. When absent, `metrics_oos_sharpe` remains null (backwards-compatible).
When present, stored as float on the Champion node.

## In Scope
- `--sharpe <float>` optional argument on `qw record --oos` path in `cli.py`
- `metrics_oos_sharpe` stored on Champion node via `store.update_champion_oos_status()`
- `data_dictionary.yaml` updated with `metrics_oos_sharpe` as nullable float on Champion
- `graph_v1_contract.md` updated — Champion property table gains `metrics_oos_sharpe`
- Runbook OOS section updated — example commands gain `--sharpe` variant
- Champion fixture OOS Command blocks updated to show `--sharpe` as optional
- Existing `test_store_oos_update.py` extended (see Test Coverage below)

## Out of Scope
- Backfilling `metrics_oos_sharpe` on existing Champion nodes
- OOS trade count, OOS return, or other OOS metrics (Sharpe only)
- Validation that OOS Sharpe is lower than IS Sharpe

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — add `--sharpe` to `--oos` argument group
- `qws_graph/research/graph/store.py` — add `sharpe: float | None = None` param to
  `update_champion_oos_status()`; write `metrics_oos_sharpe` on Champion MERGE
- `qws_graph/docs/data_dictionary.yaml` — `metrics_oos_sharpe`: nullable float on Champion
- `qws_graph/docs/graph_v1_contract.md` — Champion property table: add `metrics_oos_sharpe`
- `qws_graph/docs/qws_graph_runbook.md` — OOS recording section: add `--sharpe` example
- `qws_graph/tests/unit/test_store_oos_update.py` — extend (see below)
- `qws_graph/tests/fixtures/artifacts/champion/es_bear_sweep_1h_v1.md` — OOS Command block
- `qws_graph/tests/fixtures/artifacts/champion/nq_bull_sweep_4h_v1.md` — OOS Command block
- `qws_graph/tests/fixtures/artifacts/champion/cl_bear_sweep_1h_no_pivot.md` — OOS Command block

## Test Coverage

### Extend `test_store_oos_update.py`

**`FakeGraphStore.update_champion_oos_status()`** — add `sharpe: float | None = None` param;
record it in `self.updates` dict alongside `status` and `oos_date`.

**`_run_oos()` helper** — add `sharpe: float | None = None` param; pass through to `Namespace`.

**New test class `TestOosSharpePropagation`:**
- `test_sharpe_stored_when_passed` — `--sharpe 3.21` → `store.updates[0]["sharpe"] == 3.21`
- `test_sharpe_absent_is_none` — no `--sharpe` → `store.updates[0]["sharpe"] is None`
- `test_sharpe_stored_on_oos_fail` — `--oos oos_fail --sharpe 0.8` → stored (fail with Sharpe is valid)
- `test_sharpe_negative_rejected` — `--sharpe -1.0` → exit code 1, clear error (Sharpe cannot be negative)
- `test_sharpe_in_receipt_payload` — receipt JSON includes `"oos_sharpe": 3.21` when passed

**Extend `TestOosReceipt.test_receipt_kind_and_status`** — add assertion that
`receipt["oos_sharpe"]` is null when `--sharpe` absent.

## Fixture Updates

Champion fixture OOS Command blocks (`es_bear_sweep_1h_v1.md`, `nq_bull_sweep_4h_v1.md`,
`cl_bear_sweep_1h_no_pivot.md`) currently show bare `qw record --oos` commands. Add a
commented `--sharpe <value>` line to each, showing it as optional:

```zsh
qw record --oos pass \
  --champion <champion_id> \
  --sharpe 2.84          # optional — records OOS Sharpe for drift analysis
```

## Acceptance Criteria
- [x] `qw record --oos pass --champion <id> --sharpe 3.21` stores `metrics_oos_sharpe = 3.21`
  on the Champion node.
- [x] `qw record --oos pass --champion <id>` (no `--sharpe`) leaves `metrics_oos_sharpe` null,
  not an error.
- [x] `qw record --oos fail --champion <id> --sharpe 0.8` stores `metrics_oos_sharpe = 0.8`
  (fail with a Sharpe is valid — records what OOS actually produced).
- [x] `qw record --oos pass --champion <id> --sharpe -1.0` returns exit code 1 with a clear
  error message (negative Sharpe rejected).
- [x] Receipt JSON includes `oos_sharpe` key: float when passed, null when absent.
- [x] `data_dictionary.yaml` documents `metrics_oos_sharpe` as nullable float on Champion.
- [x] `graph_v1_contract.md` Champion property table includes `metrics_oos_sharpe`.
- [x] All three champion fixtures show `--sharpe` as an optional flag in OOS Command block.
- [x] All existing `test_store_oos_update.py` tests remain green (backwards-compatible).

## Definition of Done
- [x] CLI flag, store write implemented and tested.
- [x] All new test cases pass; all existing OOS tests remain green.
- [x] `data_dictionary.yaml`, `graph_v1_contract.md`, runbook updated.
- [x] Champion fixtures updated.
- [x] Story marked CLOSED.
