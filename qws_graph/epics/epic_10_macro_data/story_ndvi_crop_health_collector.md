# Story — NDVI Crop Health Collector

## ID
QWS-1011

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1000

## Summary
Add a NASA MODIS NDVI collector that downloads daily satellite raster products for the US corn belt, applies a cropland mask, computes mean NDVI per region, derives an anomaly signal (deviation from 5-year daily historical average), and writes results into the shared `macro` ArcticDB library via `write_series()`. Crop health during growing season is a direct price input for ZC and ZS.

## Problem
Grain strategies (ZC, ZS) have no structural awareness of in-season crop health. USDA crop progress (QWS-1006) captures development stage percentages, but not vegetative stress. NDVI anomaly is a fast signal: a sharply negative deviation during pollination (July) or grain fill (August) historically precedes supply shock revisions within days, not weeks.

## Goal
Collect daily MODIS NDVI for US corn belt regions, compute `ndvi_anomaly` as deviation from the 5-year historical daily mean, and write into ArcticDB `macro` library keyed by region. During the November–March off-season, collector no-ops cleanly.

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

- Source: NASA MODIS Terra/Aqua — MOD09GA (daily 500m surface reflectance, NDVI computed from bands 1+2)
- Auth: NASA Earthdata token — `NASA_EARTHDATA_TOKEN` env var; stored as export in `~/.zshrc`. Free account at https://urs.earthdata.nasa.gov/
- Cropland mask: static GeoTIFF mask for corn/soy pixels; applied before computing regional mean
- Derived metric: `ndvi_anomaly` = current NDVI − 5-year historical daily average for same calendar day
- Write both `ndvi` (raw) and `ndvi_anomaly` columns per series via `store.write_series()`
- Idempotent: incremental fetch from last stored date
- Off-season (November–March): collector logs INFO and exits cleanly — no error, no write

## Out of Scope
- EVI or other vegetation indices
- Sub-state (county) level resolution
- Real-time or intraday NDVI
- Graph ingestion / Regime node updates (separate story)
- Automated cropland mask generation (use static CDL mask file bundled with collector)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes

**NASA Earthdata download:**
- MODIS CMR search endpoint: `https://cmr.earthdata.nasa.gov/search/granules.json`
- Params: `short_name=MOD09GA`, `temporal={date},{date}`, `bounding_box={corn_belt_bbox}`
- Download via `earthaccess` or direct HTTPS with `Authorization: Bearer {NASA_EARTHDATA_TOKEN}`
- GeoTIFF processing: use `rasterio` to open HDF4/GeoTIFF, extract band arrays, compute NDVI = (NIR − Red) / (NIR + Red)

**Cropland mask:**
- Static CDL corn+soy mask GeoTIFF bundled at `data/collectors/assets/corn_belt_mask.tif`
- Apply with numpy boolean indexing: `ndvi_array[mask == 0] = np.nan`; `np.nanmean(ndvi_array)`

**5-year historical baseline:**
- On first run, download 5 years of MOD09GA to compute daily climatology
- Store climatology as separate `NDVI_{REGION}_CLIM_1D` series in `macro` library
- Anomaly = today's NDVI − climatology value for same day-of-year

**Config:**
- `NASA_EARTHDATA_TOKEN` loaded from env var; stored as export in `~/.zshrc` per security rules — do NOT add to `.env` or `.env.example`

**Store columns:** `ndvi` (float, 0–1 range), `ndvi_anomaly` (float, signed deviation) — no `total_` prefix, no `_usd` suffix

**Callable as** `python -m data.collectors.ndvi`

**Unit tests:** No live HTTP or raster I/O — mock download function returning fixture numpy arrays; test mask application, anomaly computation, and ArcticDB write path.

## Repo Touchpoints
- `data/collectors/ndvi.py` — new
- `data/config.py` — add `nasa_earthdata_token`
- `pyproject.toml` — add `rasterio`, `earthpy`, `numpy`
- `tests/unit/test_ndvi_collector.py` — new
- `data/collectors/assets/corn_belt_mask.tif` — new

## Acceptance Criteria
- [ ] `data/collectors/ndvi.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] `NDVI_CORN_BELT_1D` series writes with `ndvi` and `ndvi_anomaly` columns and DatetimeIndex
- [ ] All 5 state-level series write successfully
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] Off-season call (November–March): collector exits 0 with INFO log, no exception, no write
- [ ] Cropland mask applied before regional mean (non-cropland pixels excluded)
- [ ] `ndvi_anomaly` computed correctly as deviation from 5-year same-day baseline
- [ ] `nasa_earthdata_token` present in `data/config.py`
- [ ] `rasterio`, `earthpy`, `numpy` added to `pyproject.toml` dependencies
- [ ] `tests/unit/test_ndvi_collector.py` passes with mocked download and fixture arrays
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires NASA Earthdata free account (https://urs.earthdata.nasa.gov/)
- `NASA_EARTHDATA_TOKEN` set in `~/.zshrc`
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1005 (NOAA), QWS-1006 (USDA)
- Enables: satellite-derived crop stress signal for ZC and ZS strategy conditioning
