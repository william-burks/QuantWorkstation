# Story — NOAA Heating/Cooling Degree Day Collector

## ID
QWS-1005

## Status
TESTING

## Type
code

## Blocked On
None

## Summary
Add a NOAA Climate Data API collector that pulls weekly Heating Degree Days (HDD) and Cooling Degree Days (CDD) for US national and regional series and writes them into the shared `macro` ArcticDB library via `write_series()`. Primary weather input for NG strategy conditioning.

## Problem
NG strategies have no awareness of weather conditions. HDD and CDD are the standard industry inputs for estimating residential heating and cooling demand — the dominant driver of short-term natural gas consumption. Without structured degree day data, strategy signals cannot condition on or avoid high-weather-uncertainty periods.

## Goal
Collect HDD and CDD weekly series for US national and key regional aggregates via the NOAA Climate Data API, and write into ArcticDB `macro` library.

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

## Out of Scope
- Hourly or sub-weekly temperature data
- Precipitation, wind, or other climate variables
- Forecast degree days (observed only)
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- NOAA CDO API base: `https://www.ncdc.noaa.gov/cdo-web/api/v2/data`
  - Params: `datasetid=GHCND`, `datatypeid=HDD` or `CDD`, `locationid={REGION_CODE}`,
    `startdate`, `enddate`, `units=standard`
  - Auth header: `token: {NOAA_API_KEY}`
  - Response: JSON `results` array with `date` and `value` fields
- `NOAA_API_KEY` loaded from env var; stored as export in `~/.zshrc` per security rules — do NOT add to `.env` or `.env.example`
- NOAA region codes for CDO: national = `CLIM:US`, Northeast = `CLIM:R1`, Midwest = `CLIM:R4` — verify exact codes against CDO API before implementing
- Store column: `value` (degree days, float) — no `total_` prefix, no `_usd` suffix
- Callable as `python -m data.collectors.noaa`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture JSON

## Repo Touchpoints
- `data/collectors/noaa.py` — new
- `data/config.py` — add `noaa_api_key`, `noaa_series`
- `tests/unit/test_noaa_collector.py` — new

## Acceptance Criteria
- [x] `data/collectors/noaa.py` exists and is importable
- [x] `macro` ArcticDB library created on first run (or reuses existing)
- [x] All 4 series write successfully with `value` column and DatetimeIndex
- [x] Re-running collector is idempotent (appends only new dates; no duplicates)
- [x] `noaa_api_key` and `noaa_series` present in `data/config.py`
- [x] `tests/unit/test_noaa_collector.py` passes with mocked `requests.get` (no live API calls in tests)
- [x] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: noaa.py exists and is importable
- type: cli
- cmd: `python -c "from data.collectors.noaa import collect, DEFAULT_SERIES, _SERIES_MAP; print(len(DEFAULT_SERIES))"`
- expect_contains: "4"
- expect_exit: 0

### AC2: macro library used (write_series called with lib="macro")
- type: regression
- cmd: `python -m pytest tests/unit/test_noaa_collector.py::test_collect_writes_all_four_series -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC3: All 4 series write with value column and DatetimeIndex
- type: cli
- cmd: `python -m pytest tests/unit/test_noaa_collector.py::test_collect_written_df_has_value_column_and_datetime_index -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: Idempotent — incremental fetch passes start_date
- type: cli
- cmd: `python -m pytest tests/unit/test_noaa_collector.py::test_collect_incremental_passes_start_date -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: noaa_api_key and noaa_series in config.py
- type: file_check
- cmd: `python -c "from data.config import Settings; s = Settings.model_fields; print('noaa_api_key' in s and 'noaa_series' in s)"`
- expect_contains: "True"
- expect_exit: 0

### AC6: Unit tests pass with mocked requests.get
- type: cli
- cmd: `python -m pytest tests/unit/test_noaa_collector.py -v`
- expect_contains: "passed"
- expect_exit: 0

## Dependencies
- Requires NOAA API key (free registration at https://www.ncdc.noaa.gov/cdo-web/webservices/v2)
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1004 (Baker Hughes)
- Enables: weather-conditioned regime signal for NG strategies
