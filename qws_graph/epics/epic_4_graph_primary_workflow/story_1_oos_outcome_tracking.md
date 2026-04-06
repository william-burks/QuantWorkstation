# Story 1 — OOS Outcome Tracking

## ID
QWS-0402

## Status
draft

## Summary
Add `qw record --oos <status> --champion <id>` to record OOS validation outcomes directly
on Champion nodes. Closes the only missing lifecycle step in the current ingest flow.

## Problem
After running OOS validation, there is no way to record the outcome without manually
editing and re-ingesting a `champion_md` file. As a result:
- `qw query --name staleness_report` can surface unvalidated champions but can't distinguish
  "never tested" from "tested and passed."
- The `oos_status` field on Champion nodes is always `oos_pending` unless a human writes
  a new champion markdown.
- There is no `oos_date` timestamp — no way to know when the validation happened.

## Goal
A single command closes the loop:
```zsh
qw record --oos oos_pass --champion <champion_id>
qw record --oos oos_fail --champion <champion_id> --reason "drawdown exceeded -12% in OOS window"
```

This updates `oos_status` and sets `oos_date` on the existing `:Champion` node atomically.
No markdown file needs to be written or re-ingested.

## Deliverable
- `--oos` flag on `qw record` CLI subcommand
- `--champion` flag (required when `--oos` is used)
- `--reason` flag (optional, free-text; stored as `oos_reason` on Champion node)
- `store.update_champion_oos_status(champion_id, status, reason, date)` method
- Receipt written with `kind: oos_update` and `status: persisted`

## Valid `oos_status` values
- `oos_pending` — default, no validation done
- `oos_pass` — OOS validation passed
- `oos_fail` — OOS validation failed (--reason recommended)

These must be consistent with any `WHERE ch.oos_status = ...` filters in `query.py`.

## In Scope
- `qws_graph/research/graph/cli.py` — new `--oos` / `--champion` / `--reason` flags
- `qws_graph/research/graph/store.py` — `update_champion_oos_status()` method
- `qws_graph/docs/graph_v1_contract.md` — add `oos_date` and `oos_reason` to Champion spec
- Unit tests for the store method and CLI flag parsing

## Out of Scope
- OOS window definition or test execution (this story only records outcomes)
- Modifying the champion_md parser (existing markdown ingest path unchanged)
- Automated OOS scheduling

## Repo Touchpoints
- `qws_graph/research/graph/cli.py`
- `qws_graph/research/graph/store.py`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_store_oos_update.py` — new

## Acceptance Criteria
- [ ] `qw record --oos oos_pass --champion <id>` exits `0` and updates `ch.oos_status`
  and sets `ch.oos_date` on the Champion node.
- [ ] `qw record --oos oos_fail --champion <id> --reason "..."` stores reason in
  `ch.oos_reason`.
- [ ] `qw record --oos invalid_status --champion <id>` exits non-zero with a clear error.
- [ ] `qw record --oos oos_pass` without `--champion` exits non-zero.
- [ ] Receipt written with `kind: oos_update` and `status: persisted`.
- [ ] `qw query --name staleness_report` reflects updated `oos_status` after the command.
- [ ] Unit tests cover valid transition, invalid status, missing champion ID.

## Definition of Done
- [ ] Store method + CLI flag implemented and tested.
- [ ] `graph_v1_contract.md` updated with `oos_date` and `oos_reason`.
- [ ] Story marked CLOSED.
