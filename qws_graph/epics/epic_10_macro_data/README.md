# Epic 10 — Macro Data

## Objective
Wire macro and alternative data sources as inputs for regime signal generation.
All sources ingest to ArcticDB on a scheduled basis via Prefect. Validation gate
confirms data quality before downstream regime classifier (Epic 12) consumes feeds.

## Why it exists
Rule-based and ML strategies need external context signals (macro regime, commodity
fundamentals, agricultural supply shocks, sentiment proxies) to generate edge beyond
pure price action. This epic builds the ingestion layer — no strategy changes, no
graph changes, just reliable scheduled data collection.

## Stories

| ID | Name | File | Status | Blocked On |
|---|---|---|---|---|
| QWS-1001 | COT Collector | `story_cot_collector.md` | READY | — |
| QWS-1002 | FRED Macro Collector | `story_fred_macro_collector.md` | READY | — |
| QWS-1003 | EIA Crude Collector | `story_eia_crude_collector.md` | READY | — |
| QWS-1004 | Baker Hughes Rig Count | `story_baker_hughes_rig_count.md` | READY | — |
| QWS-1005 | NOAA Degree Days | `story_noaa_degree_days.md` | READY | — |
| QWS-1006 | USDA Crop Progress | `story_usda_crop_progress.md` | READY | — |
| QWS-1007 | Google Trends | `story_google_trends.md` | READY | — |
| QWS-1008 | BDTI Tanker Index | `story_bdti_tanker_index.md` | READY | — |
| QWS-1009 | Economic Calendar Collector | `story_economic_calendar_collector.md` | READY | — |
| QWS-1010 | Data Quality Validation | `story_data_quality_validation.md` | READY | — |
| QWS-1011 | NDVI Crop Health Collector | `story_ndvi_crop_health_collector.md` | READY | QWS-1001 |
| QWS-1100 | Prefect Data Collection Infra | `story_prefect_data_collection_infra.md` | READY | — |

## Dependency Notes
- QWS-1100 (Prefect) is infrastructure prerequisite for all scheduled collection jobs.
  Implement first or in parallel with early collectors.
- QWS-1011 (NDVI) is blocked on QWS-1001 (COT) — NDVI pipeline reuses COT ingestion
  patterns and ArcticDB library conventions established in QWS-1001.
- QWS-1010 (Validation) should run after first collector delivers data.
- All other stories (QWS-1001 through QWS-1009) are independent — implement in parallel.
- Epic 10 is independent of Epic 8 and Epic 11.

## Done Criteria
- All data sources ingesting to ArcticDB on Prefect schedule.
- Data quality validation gate live — alerts on missing bars, stale feeds, schema drift.
- All story files marked CLOSED.
