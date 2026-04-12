# Story — Economic Calendar Collector

## ID
QWS-1009

## Status
READY

## Date
2026-04-12

## Summary
Add a FinancialModelingPrep economic calendar collector that pulls upcoming and historical
macro events daily and writes event metadata into a new `calendar` ArcticDB library.
Provides blackout window context for strategy research — high-impact events flag periods
where alpha estimates are unreliable.

## Problem
Research pipeline has no awareness of scheduled macro events (FOMC, NFP, CPI). Strategies
that happen to trade around high-impact events can show inflated IS Sharpe from event-driven
noise that will not persist OOS. Without an event calendar, Will has no systematic way to
identify or exclude these periods during research reviews.

## Goal
Collect economic calendar events daily from FMP, write into ArcticDB `calendar` library,
and expose a boolean `is_blackout` flag for high-impact events. Research pipeline reads the
flag as advisory context — it does not gate automatically.

## Deliverable
- `data/collectors/economic_calendar.py` — FMP economic calendar collector module
- `calendar` ArcticDB library; single symbol `ECON_CALENDAR`, DatetimeIndex on `release_datetime`
- `fmp_api_key: str` config field in `data/config.py`
- `FMP_API_KEY` documented in `.env.example`
- `calendar` library registered in `_LIBRARIES` in `data/store.py`
- Daily scheduler job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_economic_calendar_collector.py`

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
- `is_blackout` computed at write time from `impact` column; advisory only — not a hard gate

## Out of Scope
- Neo4j integration — calendar is operational context, not research provenance
- `OVERLAPS_EVENT` edges on Run nodes — not in scope
- Alerting or automatic trade blocking on blackout windows
- Intraday event revision tracking (use latest FMP value)

## Implementation Notes
- API key: `FMP_API_KEY` loaded from env; add `fmp_api_key: str` to `Settings` in `data/config.py`
- Endpoint: `https://financialmodelingprep.com/api/v3/economic_calendar?from={from_date}&to={to_date}&apikey={key}`
- Response fields used: `event`, `date` (→ `release_datetime` index), `previous`, `estimate` (→ `consensus`), `actual`, `impact`
- `actual` is null in FMP response before release — store as `NaN`; do not coerce to 0
- `is_blackout = (impact == 'high')` — computed before write, stored as column
- Store via `store.write_series()` (QWS-1001 method) into `calendar` library
- Follow same collector pattern as `data/collectors/fred.py` — callable as `python -m data.collectors.economic_calendar`
- No live FMP calls in unit tests — mock `requests.get` or FMP client

## Acceptance Criteria
- [ ] `data/collectors/economic_calendar.py` exists and is importable
- [ ] `calendar` ArcticDB library added to `_LIBRARIES` in `data/store.py`
- [ ] `fmp_api_key: str` present in `data/config.py` (`Settings`)
- [ ] `FMP_API_KEY` documented in `.env.example`
- [ ] Collector writes `ECON_CALENDAR` symbol with correct columns and UTC DatetimeIndex
- [ ] `is_blackout` is `True` for all rows where `impact == 'high'`, `False` otherwise
- [ ] `actual` stored as `NaN` for pre-release events (not 0)
- [ ] Re-running collector is idempotent — no duplicate index entries
- [ ] Daily scheduler job registered and callable without error
- [ ] `tests/unit/test_economic_calendar_collector.py` passes with mocked HTTP calls
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] `ECON_CALENDAR` symbol seeded with at least 30 days of events (past + upcoming)
- [ ] Second run confirmed idempotent — no new rows appended for already-stored events
- [ ] `is_blackout` spot-checked: FOMC and NFP events show `True`
- [ ] Scheduler job confirmed callable without error
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- **Blocked on:** QWS-1001 (requires `write_series` / `read_series` store methods)
- Requires FMP API key (free registration at https://financialmodelingprep.com/developer/docs)
- Enables: macro event awareness during research session reviews
- Enables: blackout window filtering in future strategy evaluation stories
