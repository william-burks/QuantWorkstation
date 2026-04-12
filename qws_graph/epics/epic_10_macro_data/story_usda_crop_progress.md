# Story — USDA Crop Progress Collector

## ID
QWS-1006

## Status
READY

## Summary
Add a USDA NASS crop progress collector that pulls weekly planting and development stage
percentages for corn and soybeans via the NASS API and writes them into the shared `macro`
ArcticDB library. Markets trade these numbers directly during growing season (April–November);
this feeds ZC and ZS strategy conditioning.

## Problem
Grain strategies (ZC, ZS) operate without any structured awareness of crop condition.
USDA NASS releases weekly crop progress every Monday during growing season — planting pace,
emergence, silking, and harvest completion are primary price drivers. Without a collector,
this data is unavailable to the research pipeline and strategies cannot condition on
crop development stress or seasonal timing.

## Goal
Collect weekly USDA NASS crop progress percentages for corn and soybeans at national and
top-5 state level during growing season, write into ArcticDB `macro` library, and no-op
cleanly during the November–March off-season when NASS publishes no current data.

## Deliverable
- `data/collectors/usda_crop.py` — USDA crop progress collector module — **new**
- `macro` ArcticDB library; keys per pattern `USDA_{CROP}_{STAGE}_{REGION}`
  (e.g. `USDA_CORN_PLANTED_NATL`, `USDA_SOYBEAN_PLANTED_NATL`, `USDA_CORN_HARVESTED_IA`)
- `usda_api_key: str` config field in `data/config.py`
- Weekly Monday scheduler job registered in `execution/scheduler.py` (NASS releases Monday ~4pm ET)
- Unit tests in `tests/unit/test_usda_crop_collector.py`

## In Scope
Crops and stages (national + top-5 states):
| Crop | Stages | Regions |
|---|---|---|
| Corn | planted, emerged, silking, dough, dent, mature, harvested | NATL, IL, IA, IN, NE, MN |
| Soybeans | planted, emerged, blooming, setting pods, dropping leaves, harvested | NATL, IL, IA, IN, NE, MN |

- Fetch via USDA NASS Quick Stats API (`https://quickstats.nass.usda.gov/api/api_GET/`)
- Auth: `USDA_API_KEY` query param; key obtained free from NASS portal; stored as export in `~/.zshrc`
- Write weekly series via `store.write_series()` into `macro` library
- Idempotent: incremental fetch from last stored date; no full re-pull on every run
- Off-season handling: if NASS returns empty results for current year (no active survey week),
  collector logs a single INFO line and exits cleanly — no error, no write
- Scheduler: weekly Monday job (NASS releases Monday ~4pm ET during growing season only)

## Out of Scope
- Crop condition ratings (good/excellent/poor percentages) — separate series, separate story
- Cotton, wheat, or other crops
- Sub-state (district) level data
- Forecast or survey pre-release estimates
- Graph ingestion / Regime node updates (separate story)

## Implementation Notes
- NASS Quick Stats API: `https://quickstats.nass.usda.gov/api/api_GET/`
  - Params: `key={USDA_API_KEY}`, `commodity_desc=CORN` or `SOYBEANS`,
    `statisticcat_desc=PROGRESS`, `unit_desc=PCT PLANTED` (or other stage),
    `freq_desc=WEEKLY`, `state_alpha={STATE}` or omit for national,
    `year__GE={LAST_STORED_YEAR}`
  - Response: JSON `data` array with `week_ending`, `Value` fields
- `USDA_API_KEY` loaded from env var; stored as export in `~/.zshrc` per security rules —
  do NOT add to `.env` or `.env.example`
- Store column: `pct` (float, 0–100 percentage) — no `total_` prefix, no `_usd` suffix
- ArcticDB key construction: `USDA_{CROP}_{STAGE}_{REGION}` all uppercase, underscores
  (e.g. `USDA_CORN_PLANTED_NATL`, `USDA_CORN_PLANTED_IA`)
- Off-season detection: check if `week_ending` in response is current year; if no rows
  returned for current growing season, log and return without writing
- Collector callable as `python -m data.collectors.usda_crop`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture JSON

## Acceptance Criteria
- [ ] `data/collectors/usda_crop.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] National corn and soybean planted series write successfully with `pct` column and DatetimeIndex
- [ ] All top-5 state series write for at least one crop and stage combination
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] Off-season call (NASS returns empty): collector exits 0 with INFO log, no exception, no write
- [ ] `usda_api_key` present in `data/config.py`
- [ ] Weekly Monday scheduler job registered and callable without error
- [ ] `tests/unit/test_usda_crop_collector.py` passes with mocked `requests.get` including fixture for empty off-season response
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded with corn and soybean planted series for NATL + all 5 states (full available history)
- [ ] Off-season behavior confirmed with a test run returning clean no-op
- [ ] Incremental run confirmed: second run appends 0 rows, no crash
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on QWS-1001 (COT Collector) — `write_series` / `read_series` store methods land there
- Requires USDA NASS API key (free registration at https://quickstats.nass.usda.gov/api)
- Shares `macro` ArcticDB library with QWS-1002 (FRED), QWS-1003 (EIA), QWS-1004 (Baker Hughes), QWS-1005 (NOAA)
- Enables: crop-progress-conditioned seasonal signals for ZC and ZS strategies
