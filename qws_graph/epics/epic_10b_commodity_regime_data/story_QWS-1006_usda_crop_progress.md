# Story — USDA Crop Progress Collector

## ID
QWS-1006

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add a USDA NASS crop progress collector that pulls weekly planting and development stage percentages for corn and soybeans via the NASS API and writes them into the shared `macro` ArcticDB library via `write_series()`. Feeds ZC and ZS strategy conditioning.

## Problem
Grain strategies (ZC, ZS) operate without any structured awareness of crop condition. USDA NASS releases weekly crop progress every Monday during growing season — planting pace, emergence, silking, and harvest completion are primary price drivers. Without a collector, this data is unavailable to the research pipeline.

## Goal
Collect weekly USDA NASS crop progress percentages for corn and soybeans at national and top-5 state level during growing season, write into ArcticDB `macro` library, and no-op cleanly during the November–March off-season.

## In Scope
Crops and stages (national + top-5 states):
| Crop | Stages | Regions |
|---|---|---|
| Corn | planted, emerged, silking, dough, dent, mature, harvested | NATL, IL, IA, IN, NE, MN |
| Soybeans | planted, emerged, blooming, setting pods, dropping leaves, harvested | NATL, IL, IA, IN, NE, MN |

- Fetch via USDA NASS Quick Stats API (`https://quickstats.nass.usda.gov/api/api_GET/`)
- Auth: `USDA_API_KEY` query param; stored as export in `~/.zshrc`
- Write weekly series via `store.write_series()` into `macro` library
- Idempotent: incremental fetch from last stored date
- Off-season handling: if NASS returns empty results, collector logs INFO and exits cleanly — no error, no write

## Out of Scope
- Crop condition ratings (good/excellent/poor percentages)
- Cotton, wheat, or other crops
- Sub-state (district) level data
- Forecast or survey pre-release estimates
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- NASS Quick Stats API: `https://quickstats.nass.usda.gov/api/api_GET/`
  - Params: `key={USDA_API_KEY}`, `commodity_desc=CORN` or `SOYBEANS`, `statisticcat_desc=PROGRESS`, `unit_desc=PCT PLANTED` (or other stage), `freq_desc=WEEKLY`, `state_alpha={STATE}` or omit for national, `year__GE={LAST_STORED_YEAR}`
  - Response: JSON `data` array with `week_ending`, `Value` fields
- `USDA_API_KEY` loaded from env var; stored as export in `~/.zshrc` per security rules — do NOT add to `.env` or `.env.example`
- Store column: `pct` (float, 0–100 percentage) — no `total_` prefix, no `_usd` suffix
- ArcticDB key construction: `USDA_{CROP}_{STAGE}_{REGION}` all uppercase, underscores
- Callable as `python -m data.collectors.usda_crop`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture JSON

## Repo Touchpoints
- `data/collectors/usda_crop.py` — new
- `data/config.py` — add `usda_api_key`
- `tests/unit/test_usda_crop_collector.py` — new

## Acceptance Criteria
- [ ] `data/collectors/usda_crop.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] National corn and soybean planted series write successfully with `pct` column and DatetimeIndex
- [ ] All top-5 state series write for at least one crop and stage combination
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] Off-season call (NASS returns empty): collector exits 0 with INFO log, no exception, no write
- [ ] `usda_api_key` present in `data/config.py`
- [ ] `tests/unit/test_usda_crop_collector.py` passes with mocked `requests.get` including fixture for empty off-season response
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires USDA NASS API key (free registration at https://quickstats.nass.usda.gov/api)
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1004 (Baker Hughes), QWS-1005 (NOAA)
- Enables: crop-progress-conditioned seasonal signals for ZC and ZS strategies
