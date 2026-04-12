# Story — NDVI Crop Health Collector

## ID
QWS-1011

## Status
READY

## Summary
Add a NASA MODIS NDVI collector that downloads daily satellite raster products for the US
corn belt, applies a cropland mask, computes mean NDVI per region, derives an anomaly signal
(deviation from 5-year daily historical average), and writes results into the shared `macro`
ArcticDB library. Crop health during growing season (April–November) is a direct price input
for ZC and ZS.

## Problem
Grain strategies (ZC, ZS) have no structural awareness of in-season crop health. USDA crop
progress (QWS-1006) captures development stage percentages, but not vegetative stress — the
condition of the standing crop visible from satellite. NDVI anomaly is a fast signal: a
sharply negative deviation during pollination (July) or grain fill (August) historically
precedes supply shock revisions within days, not weeks.

## Goal
Collect daily MODIS NDVI for US corn belt regions, compute `ndvi_anomaly` as deviation from
the 5-year historical daily mean, and write into ArcticDB `macro` library keyed by region.
Collector runs daily (MODIS has ~1–2 day latency). During the November–March off-season,
collector no-ops cleanly.

## Deliverable
- `data/collectors/ndvi.py` — MODIS NDVI collector module — **new**
- `macro` ArcticDB library; key pattern `NDVI_{REGION}_1D`
  (e.g. `NDVI_CORN_BELT_1D`, `NDVI_IOWA_1D`, `NDVI_ILLINOIS_1D`, `NDVI_INDIANA_1D`,
  `NDVI_NEBRASKA_1D`, `NDVI_MINNESOTA_1D`)
- `nasa_earthdata_token: str` config field in `data/config.py`
- Daily scheduler job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_ndvi_collector.py`
- New dependencies added to `pyproject.toml`: `rasterio`, `earthpy`, `numpy`

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

- Source: NASA MODIS Terra/Aqua — MOD13A2 (16-day 1km NDVI) or MOD09GA (daily 500m surface reflectance, NDVI computed from bands 1+2). Use MOD09GA for daily resolution.
- Auth: NASA Earthdata token — `NASA_EARTHDATA_TOKEN` env var; stored as export in `~/.zshrc`. Free account at https://urs.earthdata.nasa.gov/
- Cropland mask: USDA CDL (Cropland Data Layer) or static GeoTIFF mask for corn/soy pixels only. Mask applied before computing regional mean.
- Derived metric: `ndvi_anomaly` = current NDVI − 5-year historical daily average for same calendar day. This is the primary signal column.
- Write both `ndvi` (raw) and `ndvi_anomaly` columns per series.
- Idempotent: incremental fetch from last stored date; no full re-pull on every run.
- Off-season (November–March): collector logs INFO and exits cleanly — no error, no write.

## Out of Scope
- EVI or other vegetation indices
- Sub-state (county) level resolution
- Real-time or intraday NDVI
- Graph ingestion / Regime node updates (separate story)
- Automated cropland mask generation (use static CDL mask file bundled with collector)

## Implementation Notes

**Complexity note:** This collector requires satellite raster processing (GeoTIFF download →
cropland mask application → regional mean aggregation). More complex than REST API collectors.
Recommended two-pass implementation:
1. Pass 1: MODIS HTTP download + raw NDVI write (raw series, no anomaly yet)
2. Pass 2: Raster crop mask + anomaly computation layer on top of Pass 1 output

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

**Collector callable as** `python -m data.collectors.ndvi`

**Unit tests:** No live HTTP or raster I/O — mock download function returning fixture numpy arrays; test mask application, anomaly computation, and ArcticDB write path.

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
- [ ] Daily scheduler job registered and callable without error
- [ ] `rasterio`, `earthpy`, `numpy` added to `pyproject.toml` dependencies
- [ ] `tests/unit/test_ndvi_collector.py` passes with mocked download and fixture arrays
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded: `NDVI_CORN_BELT_1D` + all 5 state series with 5-year history
- [ ] Climatology baseline series written (`NDVI_{REGION}_CLIM_1D`)
- [ ] Anomaly signal validated against known stress years (2012 drought: anomaly should be strongly negative July–August)
- [ ] Off-season no-op confirmed with test run
- [ ] Incremental run confirmed: second run appends 0 rows, no crash
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on QWS-1001 (COT Collector) — `write_series` / `read_series` store methods land there
- Requires NASA Earthdata free account (https://urs.earthdata.nasa.gov/)
- `NASA_EARTHDATA_TOKEN` set in `~/.zshrc`
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1005 (NOAA), QWS-1006 (USDA)
- Enables: satellite-derived crop stress signal for ZC and ZS strategy conditioning
