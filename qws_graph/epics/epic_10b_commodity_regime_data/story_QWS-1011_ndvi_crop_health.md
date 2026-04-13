# Story — NDVI Crop Health Collector

## ID
QWS-1011

## Status
TESTING

## Type
code

## Blocked On
None

## Summary
Add a NASA AppEEARS NDVI collector that requests server-side spatial subsets for US corn belt regions via the AppEEARS REST API, receives CSV output (no rasterio dep), computes mean NDVI per region, derives an anomaly signal (deviation from 5-year daily historical average), and writes results into the shared `macro` ArcticDB library via `write_series()`. Crop health during growing season is a direct price input for ZC and ZS.

## Problem
Grain strategies (ZC, ZS) have no structural awareness of in-season crop health. USDA crop progress (QWS-1006) captures development stage percentages, but not vegetative stress. NDVI anomaly is a fast signal: a sharply negative deviation during pollination (July) or grain fill (August) historically precedes supply shock revisions within days, not weeks.

## Goal
Collect daily MODIS NDVI for US corn belt regions via NASA AppEEARS REST API, compute `ndvi_anomaly` as deviation from the 5-year historical daily mean, and write into ArcticDB `macro` library keyed by region. During the November–March off-season, collector no-ops cleanly.

## In Scope

Regions and source:
| Region key | Coverage |
|---|---|
| `CORN_BELT` | Aggregate across all 5 states (area-weighted mean) |
| `IOWA` | Iowa cropland pixels |
| `ILLINOIS` | Illinois cropland pixels |
| `INDIANA` | Indiana cropland pixels |
| `NEBRASKA` | Nebraska cropland pixels |
| `MINNESOTA` | Minnesota cropland pixels |

- Source: NASA AppEEARS REST API — server-side spatial subset, returns CSV, no rasterio dep
- Auth: NASA Earthdata token — `NASA_EARTHDATA_TOKEN` env var; stored as export in `~/.zshrc`. Free account at https://urs.earthdata.nasa.gov/
- Derived metric: `ndvi_anomaly` = current NDVI − 5-year historical daily average for same calendar day
- Write both `ndvi` (raw) and `ndvi_anomaly` columns per series via `store.write_series()`
- Idempotent: incremental fetch from last stored date
- Off-season (November–March): collector logs INFO and exits cleanly — no error, no write

## Out of Scope
- EVI or other vegetation indices
- Sub-state (county) level resolution
- Real-time or intraday NDVI
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1013)

## Implementation Notes

**NASA AppEEARS REST API:**
- AppEEARS task submission: `POST https://appeears.earthdatacloud.nasa.gov/api/task`
- Auth: Bearer token obtained via `POST /api/login` with NASA Earthdata credentials
- Request type: `point` or `area` with GeoJSON polygon for corn belt bounding box
- Product: `MOD13Q1.061` (MODIS Terra Vegetation Indices, 16-day, 250m) or `MYD13Q1.061` for combined
- Response: CSV files returned via `GET /api/bundle/{task_id}` — no rasterio, no HDF4 download required
- Parse CSV: date column + NDVI column; aggregate across sample points for regional mean

**5-year historical baseline:**
- On first run, submit AppEEARS task spanning 5 years to compute daily climatology
- Store climatology as separate `NDVI_{REGION}_CLIM_1D` series in `macro` library
- Anomaly = today's NDVI − climatology value for same day-of-year

**Config:**
- `NASA_EARTHDATA_TOKEN` loaded from env var; stored as export in `~/.zshrc` per security rules — do NOT add to `.env` or `.env.example`

**Store columns:** `ndvi` (float, 0–1 range), `ndvi_anomaly` (float, signed deviation) — no `total_` prefix, no `_usd` suffix

**Callable as** `python -m data.collectors.ndvi`

**Unit tests:** No live HTTP — mock AppEEARS API responses returning fixture CSV content; test anomaly computation and ArcticDB write path.

## Repo Touchpoints
- `data/collectors/ndvi.py` — new
- `data/config.py` — add `nasa_earthdata_token`
- `pyproject.toml` — add `numpy` (no rasterio dep)
- `tests/unit/test_ndvi_collector.py` — new

## Acceptance Criteria
- [x] `data/collectors/ndvi.py` exists and is importable
- [x] `macro` ArcticDB library created on first run (or reuses existing)
- [x] `NDVI_CORN_BELT_1D` series writes with `ndvi` and `ndvi_anomaly` columns and DatetimeIndex
- [x] All 5 state-level series write successfully
- [x] Re-running collector is idempotent (appends only new dates; no duplicates)
- [x] Off-season call (November–March): collector exits 0 with INFO log, no exception, no write
- [x] `ndvi_anomaly` computed correctly as deviation from 5-year same-day baseline
- [x] `nasa_earthdata_token` present in `data/config.py`
- [x] No `rasterio` or `earthaccess` dependency added to `pyproject.toml`
- [x] `tests/unit/test_ndvi_collector.py` passes with mocked AppEEARS responses and fixture CSV
- [x] `make verify` passes

## Acceptance Test Plan

### AC1: ndvi.py exists and is importable
- type: file_check
- cmd: `python -c "from data.collectors.ndvi import collect, REGIONS, _is_off_season; print('ok')"`
- expect_contains: "ok"
- expect_exit: 0

### AC2: Off-season no-op
- type: cli
- cmd: `python -c "from unittest.mock import patch; from data.collectors.ndvi import collect; [open('/dev/null').read() for _ in []]; patch('data.collectors.ndvi._is_off_season', return_value=True).__enter__(); collect()"`
- expect_contains: (no exception)
- expect_exit: 0

### AC3: Unit tests pass with mocked AppEEARS responses
- type: cli
- cmd: `pytest tests/unit/test_ndvi_collector.py -v`
- expect_contains: "41 passed"
- expect_exit: 0

### AC4: nasa_earthdata_token in config.py
- type: file_check
- cmd: `python -c "from data.config import Settings; s = Settings.model_fields; print('present' if 'nasa_earthdata_token' in s else 'missing')"`
- expect_contains: "present"
- expect_exit: 0

### AC5: No rasterio or earthaccess in pyproject.toml
- type: file_check
- cmd: `python -c "import pathlib; txt = pathlib.Path('pyproject.toml').read_text(); print('clean' if 'rasterio' not in txt and 'earthaccess' not in txt else 'FAIL')"`
- expect_contains: "clean"
- expect_exit: 0

### AC6: ndvi_anomaly computation correctness
- type: regression
- cmd: `pytest tests/unit/test_ndvi_collector.py::test_compute_anomaly_zero_when_ndvi_equals_clim tests/unit/test_ndvi_collector.py::test_compute_anomaly_positive_when_ndvi_above_clim tests/unit/test_ndvi_collector.py::test_compute_anomaly_negative_when_ndvi_below_clim -v`
- expect_contains: "3 passed"
- expect_exit: 0

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires NASA Earthdata free account (https://urs.earthdata.nasa.gov/)
- `NASA_EARTHDATA_TOKEN` set in `~/.zshrc`
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1005 (NOAA), QWS-1006 (USDA)
- Enables: satellite-derived crop stress signal for ZC and ZS strategy conditioning
