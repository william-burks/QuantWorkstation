# Story — NOAA Heating/Cooling Degree Day Collector

## ID
QWS-1005

## Status
READY

## Summary
Add a NOAA Climate Data API collector that pulls weekly Heating Degree Days (HDD) and
Cooling Degree Days (CDD) for US national and regional series and writes them into the
shared `macro` ArcticDB library. Temperature directly drives natural gas demand; this
provides the primary weather input for NG strategy conditioning.

## Problem
NG strategies have no awareness of weather conditions. HDD and CDD are the standard
industry inputs for estimating residential heating and cooling demand — the dominant
driver of short-term natural gas consumption. Without structured degree day data, strategy
signals cannot condition on or avoid high-weather-uncertainty periods.

## Goal
Collect HDD and CDD weekly series for US national and key regional aggregates via the
NOAA Climate Data API, and write into ArcticDB `macro` library on a daily update schedule.

## Deliverable
- `data/collectors/noaa.py` — NOAA collector module — **new**
- `macro` ArcticDB library; keys per pattern `NOAA_HDD_{REGION}`, `NOAA_CDD_{REGION}`
  (e.g. `NOAA_HDD_NATIONAL`, `NOAA_CDD_NATIONAL`, `NOAA_HDD_NORTHEAST`, `NOAA_HDD_MIDWEST`)
- `noaa_api_key: str` and `noaa_series: list[str]` config fields in `data/config.py`
- Daily scheduler job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_noaa_collector.py`

## In Scope
Series to collect (initial set):
| ArcticDB Key | Description |
|---|---|
| `NOAA_HDD_NATIONAL` | US national Heating Degree Days |
| `NOAA_CDD_NATIONAL` | US national Cooling Degree Days |
| `NOAA_HDD_NORTHEAST` | Northeast region HDD |
| `NOAA_HDD_MIDWEST` | Midwest region HDD (corn belt / NG demand center) |

- Fetch via NOAA Climate Data API (`https://www.ncdc.noaa.gov/cdo-web/api/v2/data`)
- Auth: `NOAA_API_KEY` header; key obtained free from NOAA CDO portal; stored as export in `~/.zshrc`
- Write weekly series via `store.write_series()` into `macro` library
- Idempotent: incremental fetch from last stored date; no full re-pull on every run
- Scheduler: daily job (NOAA data lags ~1 day; daily run catches latest available)

## Out of Scope
- Hourly or sub-weekly temperature data
- Precipitation, wind, or other climate variables
- Forecast degree days (observed only)
- Graph ingestion / Regime node updates (separate story)

## Implementation Notes
- NOAA CDO API base: `https://www.ncdc.noaa.gov/cdo-web/api/v2/data`
  - Params: `datasetid=GHCND`, `datatypeid=HDD` or `CDD`, `locationid={REGION_CODE}`,
    `startdate`, `enddate`, `units=standard`
  - Auth header: `token: {NOAA_API_KEY}`
  - Response: JSON `results` array with `date` and `value` fields
- `NOAA_API_KEY` loaded from env var; stored as export in `~/.zshrc` per security rules —
  do NOT add to `.env` or `.env.example`
- NOAA region codes for CDO: national = `CLIM:US`, Northeast = `CLIM:R1`, Midwest = `CLIM:R4`
  — verify exact codes against CDO API before implementing
- Store column: `value` (degree days, float) — no `total_` prefix, no `_usd` suffix
- Collector callable as `python -m data.collectors.noaa`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture JSON

## Acceptance Criteria
- [ ] `data/collectors/noaa.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] All 4 series write successfully with `value` column and DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] `noaa_api_key` and `noaa_series` present in `data/config.py`
- [ ] Daily scheduler job registered and callable without error
- [ ] `tests/unit/test_noaa_collector.py` passes with mocked `requests.get` (no live API calls in tests)
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded with all 4 NOAA series (full available history via API)
- [ ] Incremental run confirmed: second run appends 0 rows, no crash
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on QWS-1001 (COT Collector) — `write_series` / `read_series` store methods land there
- Requires NOAA API key (free registration at https://www.ncdc.noaa.gov/cdo-web/webservices/v2)
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1004 (Baker Hughes)
- Enables: weather-conditioned regime signal for NG strategies
