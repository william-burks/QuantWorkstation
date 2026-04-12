# Story — EIA Crude Oil Inventory Collector

## ID
QWS-1003

## Status
READY

## Summary
Add an EIA crude oil inventory collector that pulls weekly petroleum stock series via the
EIA open data REST API and writes them into the shared `macro` ArcticDB library. Provides
CL strategy regime context — inventory surprise and release-window flags for strategy
signal conditioning.

## Problem
CL strategies operate without any awareness of weekly EIA inventory prints. The Wednesday
10:30am ET release moves crude prices consistently; entering into the print is a known edge
destroyer. Without structured inventory data, Regime tagging cannot distinguish
supply-shock weeks from baseline, and strategies have no mechanism to avoid release windows.

## Goal
Collect 4 key EIA petroleum stock series weekly, derive an inventory surprise column, write
into ArcticDB `macro` library, and register a weekly Wednesday scheduler job. No graph
changes required — this is pure data infrastructure.

## Deliverable
- `data/collectors/eia.py` — EIA collector module
- `macro` ArcticDB library; keys `EIA_{SERIES_ID}` (e.g. `EIA_WCRSTUS1`)
- `eia_api_key: str` and `eia_series: list[str]` config fields in `data/config.py`
- Weekly collection job registered in `execution/scheduler.py` (Wednesday, after 11:00 ET)
- Unit tests in `tests/unit/test_eia_collector.py`

## In Scope
Series to collect (initial set):
| Series ID | Description |
|---|---|
| `WCRSTUS1` | US crude oil stocks (total) — headline number |
| `WCSSTUS1` | Cushing, OK crude oil stocks |
| `WGTSTUS1` | US total gasoline stocks |
| `WDISTUS1` | US distillate fuel oil stocks |

- Fetch via EIA v2 REST API (`https://api.eia.gov/v2/petroleum/stoc/wstk/data/`)
- Write weekly series via `store.write_series()` into `macro` library (shared with QWS-1002)
- Stored columns per series: `value` (raw inventory level, thousands barrels), `surprise`
  (derived: `value - value.shift(1)`, i.e. week-over-week change)
- Idempotent: incremental fetch from last stored date; no full re-pull on every run
- Scheduler: weekly Wednesday job (after 11:00 ET, after EIA 10:30am release)

## Out of Scope
- Forecast/consensus data (analyst estimate vs actual surprise) — no public free source
- EIA series beyond petroleum stocks (natural gas, refined products detail)
- Graph ingestion / Regime node updates (separate story)
- Backfill beyond EIA API max history on first seed

## Implementation Notes
- EIA v2 API endpoint: `https://api.eia.gov/v2/petroleum/stoc/wstk/data/`
  - Params: `api_key`, `frequency=weekly`, `data[]=value`, `facets[series][]=PET.{SERIES_ID}.W`
  - Response: JSON `response.data` array, fields `period` (YYYY-MM-DD), `value`
- `eia_api_key` loaded from env var `EIA_API_KEY`; stored as export in `~/.zshrc` per
  security rules — do NOT add to `.env` or `.env.example`
- Library key pattern: `EIA_{SERIES_ID}` (e.g. `EIA_WCRSTUS1`) — uppercase, no frequency suffix
- `surprise` column computed after fetch: `df['surprise'] = df['value'].diff(1)` — write
  both columns together; `surprise` is NaN for the oldest row on first seed
- Incremental fetch: read last stored date via `store.read_series()`, pass `start` param to EIA
- Shares `write_series` / `read_series` store methods introduced in QWS-1001
- Follow same collector pattern as `alpaca_crypto.py` — module callable as
  `python -m data.collectors.eia`
- No live EIA API calls in unit tests — mock `requests.get`

## Acceptance Criteria
- [ ] `data/collectors/eia.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing from QWS-1002)
- [ ] All 4 series write successfully with `value` and `surprise` columns, DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] `eia_api_key` and `eia_series` present in `data/config.py`
- [ ] Weekly Wednesday scheduler job registered and callable without error
- [ ] `tests/unit/test_eia_collector.py` passes with mocked `requests.get`
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded with all 4 EIA series (full available history)
- [ ] Incremental run confirmed: second run appends 0 rows, no crash
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on QWS-1001 (COT Collector) — `write_series` / `read_series` store methods land there
- Requires EIA API key (free registration at https://www.eia.gov/opendata/)
- Shares `macro` ArcticDB library with QWS-1002 (FRED Macro Collector)
- Enables: CL inventory-surprise regime signal; release-window avoidance logic
- Enables: macro-conditioned regime tagging (future story)
