# Story 0 — Store Series Methods

## ID
QWS-1000

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add `write_series(lib, symbol, df)` and `read_series(lib, symbol, *, start, end)` methods to `data/store.py` for storing non-OHLCV time series (single or multi-column). All Epic 10 collectors use these methods.

## Problem
`write_bars()` enforces OHLCV structure. Epic 10 collectors store macro data — single `value` columns (FRED, EIA) or multi-column non-bar data (COT: `comm_net`, `noncomm_net`, `open_interest`). No correct store interface exists for this shape.

## Goal
Collectors that store macro data have a correct, tested store interface. `write_bars()` remains for OHLCV only; `write_series`/`read_series` handle everything else.

## Design
- `write_series(lib, symbol, df)` — writes `df` to ArcticDB `lib/symbol`; idempotent (upsert/append — overlapping date ranges do not create duplicate index entries)
- `read_series(lib, symbol, *, start=None, end=None)` — reads and returns the stored DataFrame; `start`/`end` are optional ISO date strings
- No schema enforcement — caller owns column names
- Same library lookup pattern as `write_bars`/`read_bars`

## In Scope
- Both methods in `data/store.py`
- Unit tests: write, read, idempotent overwrite, incremental append, date-range filtering

## Out of Scope
- Column validation or type coercion
- Migration of existing OHLCV data
- New ArcticDB libraries (callers create as needed)

## Repo Touchpoints
- `data/store.py` — add `write_series`, `read_series`
- `tests/unit/test_store_series.py` — new

## Acceptance Criteria
- [ ] `write_series` exists in `data/store.py` and is importable
- [ ] `read_series` exists in `data/store.py` and is importable
- [ ] `write_series` followed by `read_series` on same symbol returns identical DataFrame
- [ ] Calling `write_series` twice with overlapping date ranges does not create duplicate index entries
- [ ] `read_series` with `start`/`end` returns only rows within specified range
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED
