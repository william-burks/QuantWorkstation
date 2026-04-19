# Epic 10b — Commodity Regime Data

## Objective
Ingest weather and crop alternative data for NG/ZC/ZS regime conditioning. Extends Epic 10 infrastructure (write_series/read_series live).

## Entry criteria
QWS-1000 CLOSED (satisfied). MANIFESTO instrument list updated to include NG, ZC, ZS.

## Stories
- QWS-1005 — NOAA Degree Days (NG)
- QWS-1006 — USDA Crop Progress (ZC/ZS)
- QWS-1011 — NDVI Crop Health (ZC/ZS, AppEEARS path)
- QWS-1013 — Macro Collection Prefect Flow

## Dependencies
Epic 10 COMPLETE (infrastructure reused). All 4 stories independent — implement in parallel.
