# Story — Economic Calendar Collector

## ID
QWS-1009

## Status
TESTING

## Type
code

## Blocked On
None

## Summary
Add a FinancialModelingPrep economic calendar collector that pulls upcoming and historical macro events daily and writes event metadata into a new `calendar` ArcticDB library via `write_series()`. Provides blackout window context for strategy research.

## Problem
Research pipeline has no awareness of scheduled macro events (FOMC, NFP, CPI). Strategies that happen to trade around high-impact events can show inflated IS Sharpe from event-driven noise that will not persist OOS. Without an event calendar, there is no systematic way to identify or exclude these periods during research reviews.

## Goal
Collect economic calendar events daily from FMP, write into ArcticDB `calendar` library, and expose a boolean `is_blackout` flag for high-impact events. Research pipeline reads the flag as advisory context — it does not gate automatically.

## In Scope

**Storage shape:**

| Column | Type | Notes |
|---|---|---|
| `event_name` | `str` | FMP `event` field |
| `previous` | `float` | Prior release value; null if unavailable |
| `consensus` | `float` | Analyst estimate; null if unavailable |
| `actual` | `float` | Confirmed release value; null before release |
| `impact` | `str` | `high` / `medium` / `low` (from FMP `impact` field) |
| `is_blackout` | `bool` | `True` where `impact == 'high'` |

- Index: `release_datetime` (UTC-aware DatetimeIndex)
- Single symbol: `ECON_CALENDAR`
- Daily pull via FMP `/v3/economic_calendar` endpoint (free tier, 250 calls/day)
- Idempotent: fetch events for rolling window (e.g., -7 days to +30 days); upsert by `release_datetime`
- `is_blackout` computed at write time from `impact` column; advisory only
- `calendar` library registered in `_LIBRARIES` in `data/store.py`

## Out of Scope
- Neo4j integration — calendar is operational context, not research provenance
- `OVERLAPS_EVENT` edges on Run nodes
- Alerting or automatic trade blocking on blackout windows
- Intraday event revision tracking (use latest FMP value)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- API key: `FMP_API_KEY` loaded from env; add `fmp_api_key: str` to `Settings` in `data/config.py`; add to `.env.example`
- Endpoint: `https://financialmodelingprep.com/api/v3/economic_calendar?from={from_date}&to={to_date}&apikey={key}`
- Response fields used: `event`, `date` (→ `release_datetime` index), `previous`, `estimate` (→ `consensus`), `actual`, `impact`
- `actual` is null in FMP response before release — store as `NaN`; do not coerce to 0
- `is_blackout = (impact == 'high')` — computed before write, stored as column
- Store via `store.write_series()` into `calendar` library
- Callable as `python -m data.collectors.economic_calendar`
- No live FMP calls in unit tests — mock `requests.get`

## Repo Touchpoints
- `data/collectors/economic_calendar.py` — new
- `data/store.py` — add `calendar` library to `_LIBRARIES`
- `data/config.py` — add `fmp_api_key`
- `tests/unit/test_economic_calendar_collector.py` — new

## Acceptance Criteria
- [x] `data/collectors/economic_calendar.py` exists and is importable
- [x] `calendar` ArcticDB library added to `_LIBRARIES` in `data/store.py`
- [x] `fmp_api_key: str` present in `data/config.py` (`Settings`)
- [ ] `FMP_API_KEY` documented in `.env.example` — MANUAL: agent-guard blocks writes to .env files; add `FMP_API_KEY=your_fmp_api_key_here` to `.env.example` manually
- [x] Collector writes `ECON_CALENDAR` symbol with correct columns and UTC DatetimeIndex
- [x] `is_blackout` is `True` for all rows where `impact == 'high'`, `False` otherwise
- [x] `actual` stored as `NaN` for pre-release events (not 0)
- [x] Re-running collector is idempotent — no duplicate index entries (delegated to `write_series` which deduplicates by index)
- [x] `tests/unit/test_economic_calendar_collector.py` passes with mocked HTTP calls
- [ ] `make verify` passes — blocked by pre-existing lint errors in bdti/cot/eia/baker_hughes (unused ignore comments); typecheck clean for new code

## Acceptance Test Plan

### AC1: economic_calendar.py importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.collectors.economic_calendar import collect, ARC_SYMBOL, ARC_LIB; print(ARC_SYMBOL, ARC_LIB)"`
- expect_contains: "ECON_CALENDAR calendar"
- expect_exit: 0

### AC2: calendar library in _LIBRARIES
- type: file_check
- cmd: `grep 'calendar' /Users/will/ClaudeProjects/QuantWorkstation/data/store.py`
- expect_contains: "calendar"
- expect_exit: 0

### AC3: fmp_api_key in Settings
- type: file_check
- cmd: `grep 'fmp_api_key' /Users/will/ClaudeProjects/QuantWorkstation/data/config.py`
- expect_contains: "fmp_api_key"
- expect_exit: 0

### AC4: .env.example — MANUAL (agent-guard blocks)
- type: file_check
- cmd: manual — add `FMP_API_KEY=your_fmp_api_key_here` to `.env.example`
- expect_contains: "FMP_API_KEY"

### AC5+AC6+AC7: columns, is_blackout, NaN actual
- type: regression
- cmd: `source .venv/bin/activate && pytest tests/unit/test_economic_calendar_collector.py -v 2>&1 | tail -30`
- expect_contains: "passed"
- expect_exit: 0

### AC8: idempotent upsert
- type: regression
- cmd: same pytest run covers this via write_series mock tests
- expect_contains: "passed"
- expect_exit: 0

### AC9: unit tests pass
- type: cli
- cmd: `source .venv/bin/activate && pytest tests/unit/test_economic_calendar_collector.py -v 2>&1 | tail -10`
- expect_contains: "passed"
- expect_exit: 0

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires FMP API key (free registration at https://financialmodelingprep.com/developer/docs)
- Enables: macro event awareness during research session reviews
- Enables: blackout window filtering in future strategy evaluation stories
