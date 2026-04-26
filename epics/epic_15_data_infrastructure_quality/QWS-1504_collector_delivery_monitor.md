# Story — Collector Delivery Monitor

## ID
QWS-1504

## Status
PLANNED

## Type
code

## Blocked On
None

## Summary
Add `scripts/check_feeds.py` to give the researcher a fast, cron-safe check that last night's data collection ran and delivered.

## Problem
Prefect flows run overnight. No fast way to confirm collection succeeded before trusting bars in a research session. Researcher may run trials on stale data with no signal.

## Goal
A script that enumerates all symbols in `crypto` + `futures` libs, checks freshness via `Store.get_symbol_info()`, prints STALE/OK per feed, and exits non-zero on any STALE.

## Design
- Use `Store.get_symbol_info()` — not `symbol_meta()` which does a full bar read; at 216+ symbols, `symbol_meta()` would take several minutes
- Enumerate `store.list_symbols('crypto')` + `store.list_symbols('futures')` — not `Settings.futures_symbols` (not all TFs may be seeded); skip `futures_meta`
- Expected bar spacing inferred from symbol key suffix (same as QWS-1501)
- STALE threshold: `last_update_time > 2 × expected_spacing` from now
- `Store.get_symbol_info(library, symbol)` is a prerequisite — implement if not already added by QWS-1501

## In Scope
- `scripts/check_feeds.py` — new; enumerates all symbols in `crypto` + `futures` libs; uses `get_symbol_info()` for `last_update_time`; prints `symbol | tf | last_ts | expected | age | status`; non-zero exit on any STALE
- `data/store.py` — new `Store.get_symbol_info(library, symbol)` if not already added by QWS-1501
- `docs/RESEARCH_WORKFLOW.md` — `## Session Startup` section (added by QWS-1501) gains `python scripts/check_feeds.py` as second startup command

## Repo Touchpoints
- `scripts/check_feeds.py` — new; full implementation as described above
- `data/store.py` — `Store.get_symbol_info(library, symbol)` (add if QWS-1501 not yet merged)
- `docs/RESEARCH_WORKFLOW.md` — append `python scripts/check_feeds.py` to `## Session Startup` section

## Acceptance Criteria
- [ ] Covers all symbols in `crypto` + `futures` libs; skips `futures_meta`
- [ ] STALE if `last_update_time` > 2× bar spacing from now
- [ ] Output table matches specified columns: `symbol | tf | last_ts | expected | age | status`
- [ ] Non-zero exit on any STALE
- [ ] Runs in <15s for current symbol count (verified via `time`)
- [ ] `RESEARCH_WORKFLOW.md` `## Session Startup` section includes `python scripts/check_feeds.py` as the second startup command

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: covers crypto + futures, skips futures_meta
- type: cli
- cmd: `python scripts/check_feeds.py 2>&1 | grep -c "futures_meta"`
- expect: 0

### AC2: STALE threshold = 2× bar spacing
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_check_feeds.py -k "stale_threshold" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: output table columns match spec
- type: cli
- cmd: `python scripts/check_feeds.py 2>&1 | head -3`
- expect_contains: "symbol"
- expect_contains: "last_ts"
- expect_contains: "status"

### AC4: non-zero exit on STALE
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_check_feeds.py -k "stale_exit_nonzero" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC5: performance <15s
- type: cli
- cmd: `time python scripts/check_feeds.py 2>&1 | tail -3`
- expect: elapsed < 15s

### AC6: RESEARCH_WORKFLOW.md updated
- type: file_check
- cmd: `grep -n "check_feeds" docs/RESEARCH_WORKFLOW.md`
- expect_contains: "check_feeds"
- expect_exit: 0
