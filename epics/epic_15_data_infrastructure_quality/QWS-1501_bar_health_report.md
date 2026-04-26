# Story — ArcticDB Bar Health Report

## ID
QWS-1501

## Status
PLANNED

## Type
code

## Blocked On
None

## Summary
Add `scripts/bar_health.py` and `audit_symbol()` to give the researcher a fast, authoritative audit of stored bar data before running a trial.

## Problem
No current way to answer "are the bars in ArcticDB right now clean?" without writing a one-off script. Pre-session bar auditing is impossible. Trials run on data assumed clean.

## Goal
A script that enumerates all symbols in `crypto` + `futures` libs, runs gap/stale/OHLC sanity checks, outputs a per-symbol summary table, and exits non-zero on any P1 violation.

## Design
- Use `Store.get_symbol_info()` (wraps ArcticDB `lib.get_description(symbol)`) for cheap per-symbol metadata; only fall back to `read_bars()` for gap detection which requires the full index
- Add `audit_symbol(library, symbol) -> dict` to `data/validation.py` — different signature from `validate_bars(df, freq)` (which takes a DataFrame); `audit_symbol` takes (lib, symbol) and calls store internally
- Script must enumerate `store.list_symbols('crypto')` and `store.list_symbols('futures')` — do NOT enumerate `futures_meta` lib
- Symbol key suffix parsing needed to infer timeframe for gap checks — reuse `_FUTURES_KEY_RE` pattern from `store.py`; all suffixes (`1H`, `4H`, `1D`, `1W`, etc.) must be verified to parse correctly with `pd.tseries.frequencies.to_offset()`
- `Store.get_symbol_info(library, symbol)` is a prerequisite — implement it as first step of this story if not already added

## In Scope
- `scripts/bar_health.py` — new script; enumerates crypto + futures libs; outputs per-symbol summary table; non-zero exit on P1 violation
- `data/validation.py` — new `audit_symbol(library, symbol) -> dict` function
- `data/store.py` — new `Store.get_symbol_info(library, symbol)` wrapping `lib.get_description(symbol)`
- `docs/RESEARCH_WORKFLOW.md` — new `## Session Startup` section with `python scripts/bar_health.py` and decision gate

## Out of Scope
- `futures_meta` lib enumeration
- Statistical baseline / z-score anomaly detection
- Collection run ledger

## Repo Touchpoints
- `scripts/bar_health.py` — new; uses `get_symbol_info()` fast path + `audit_symbol()` for full checks; outputs `symbol | rows | date_range | gap_count | stale | violations | status` table; non-zero exit on P1
- `data/validation.py` — new `audit_symbol(library, symbol) -> dict`
- `data/store.py` — new `Store.get_symbol_info(library, symbol)` wrapping `lib.get_description(symbol)`
- `docs/RESEARCH_WORKFLOW.md` — new `## Session Startup` section

## Acceptance Criteria
- [ ] Runs against live ArcticDB; covers `crypto` + `futures` libs; skips `futures_meta`
- [ ] Output table matches specified columns: `symbol | rows | date_range | gap_count | stale | violations | status`
- [ ] Non-zero exit on any P1 violation
- [ ] Performance: `time python scripts/bar_health.py` completes in <30s using `get_symbol_info()` fast path
- [ ] `RESEARCH_WORKFLOW.md` gains a `## Session Startup` section with the exact command `python scripts/bar_health.py` and a decision gate: "P1 violation = halt session, investigate before running trials"

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: covers crypto + futures, skips futures_meta
- type: cli
- cmd: `python scripts/bar_health.py 2>&1 | grep -c "futures_meta"`
- expect: 0 (no futures_meta lines in output)

### AC2: output table columns match spec
- type: cli
- cmd: `python scripts/bar_health.py 2>&1 | head -5`
- expect_contains: "symbol"
- expect_contains: "rows"
- expect_contains: "gap_count"
- expect_contains: "status"

### AC3: non-zero exit on P1 violation
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_bar_health.py -k "p1_violation" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: performance <30s
- type: cli
- cmd: `time python scripts/bar_health.py 2>&1 | tail -3`
- expect: elapsed < 30s

### AC5: RESEARCH_WORKFLOW.md updated
- type: file_check
- cmd: `grep -n "Session Startup" docs/RESEARCH_WORKFLOW.md`
- expect_contains: "Session Startup"
- expect_exit: 0
