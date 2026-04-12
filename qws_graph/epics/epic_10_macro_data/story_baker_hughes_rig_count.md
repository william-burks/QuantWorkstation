# Story — Baker Hughes Rig Count Collector

## ID
QWS-1004

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1000

## Summary
Add a Baker Hughes North America rig count collector that downloads the weekly Excel/CSV from Baker Hughes' public website and writes US and Canada rig count series into the shared `macro` ArcticDB library via `write_series()`. Direct supply signal for CL and NG strategies.

## Problem
CL and NG strategies have no structured view of drilling activity. Baker Hughes rig count is a free, widely-followed weekly leading indicator of crude and gas supply — rising rigs precede production increases by 6–9 months. Without a collector, this signal is unavailable to strategy conditioning and regime context.

## Goal
Download Baker Hughes weekly North America rig count Excel, extract US total, US oil, US gas, and Canada counts, and write as weekly time series into ArcticDB `macro` library.

## In Scope
Series to collect (weekly):
| ArcticDB Key | Description |
|---|---|
| `BHI_US_TOTAL_RIGS` | US total rig count |
| `BHI_US_OIL_RIGS` | US oil-directed rig count |
| `BHI_US_GAS_RIGS` | US gas-directed rig count |
| `BHI_CANADA_RIGS` | Canada total rig count |

- Download weekly Excel from Baker Hughes public URL via `requests`
- Parse with `openpyxl` or `pandas.read_excel`; extract North America data sheet
- Write weekly series via `store.write_series()` into `macro` library
- Idempotent: read last stored date via `store.read_series()`; append only new rows

## Out of Scope
- International rig count (non-NA regions)
- Rig count by basin or play
- Historical backfill beyond what Baker Hughes provides in the standard download
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- Baker Hughes download page: `https://rigcount.bakerhughes.com/na-rig-count`
  — verify exact Excel URL before implementing; URL may change on site refresh
- Download is a free public Excel; no API key required
- Callable as `python -m data.collectors.baker_hughes`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture bytes
- Store columns: `count` (integer rig count per series) — no `total_` prefix, no `_usd` suffix
- Weekly index on report date (Friday release date)

## Repo Touchpoints
- `data/collectors/baker_hughes.py` — new
- `data/config.py` — update for any new settings (URL is hardcoded in module; no config field needed)
- `tests/unit/test_baker_hughes_collector.py` — new

## Acceptance Criteria
- [ ] `data/collectors/baker_hughes.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] All 4 series (`BHI_US_TOTAL_RIGS`, `BHI_US_OIL_RIGS`, `BHI_US_GAS_RIGS`, `BHI_CANADA_RIGS`) write successfully with `count` column and DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates on second run)
- [ ] `tests/unit/test_baker_hughes_collector.py` passes with mocked HTTP response (no live download in tests)
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- No API key required (public download)
- Shares `macro` ArcticDB library with QWS-1002 (FRED) and QWS-1003 (EIA)
- Enables: rig-count-conditioned supply regime signal for CL and NG strategies
