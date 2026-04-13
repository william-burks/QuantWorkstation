# Story — Baltic Dirty Tanker Index Collector

## ID
QWS-1008

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add a Baltic Dirty Tanker Index (BDTI) collector that pulls the daily index value via the Nasdaq Data Link (Quandl) API and writes it into the shared `macro` ArcticDB library via `write_series()`. Leading indicator for CL strategies.

## Problem
CL strategies have no structured view of tanker freight rates. The BDTI measures the cost of moving crude oil by sea; rate spikes precede demand-driven inventory draws, and rate collapses indicate weakening crude demand before the signal appears in EIA prints. Without a collector, this leading indicator is absent from the research pipeline.

## Goal
Collect BDTI daily index values via Nasdaq Data Link API, write into ArcticDB `macro` library, and make the series available for CL strategy conditioning and regime context.

## In Scope
| ArcticDB Key | Description |
|---|---|
| `BDTI_1D` | Baltic Dirty Tanker Index, daily close |

- Fetch via Nasdaq Data Link REST API
  - Dataset: `BWAVE/BDTI` (Baltic Exchange via Nasdaq Data Link free tier)
  - Endpoint: `https://data.nasdaq.com/api/v3/datasets/BWAVE/BDTI.json`
  - Auth: `api_key` query param; key from `NDAQ_API_KEY` env var; stored as export in `~/.zshrc`
- Write daily series via `store.write_series()` into `macro` library
- Idempotent: incremental fetch from last stored date via `?start_date=` param

## Out of Scope
- Baltic Clean Tanker Index (BCTI) or Baltic Dry Index (BDI)
- Intraday or route-level breakdown
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- Nasdaq Data Link API: `https://data.nasdaq.com/api/v3/datasets/BWAVE/BDTI.json`
  - Params: `api_key={NDAQ_API_KEY}`, `start_date={LAST_STORED_DATE}`, `order=asc`
  - Response: JSON `dataset.data` array, columns `[date, value]`
  - Verify dataset code `BWAVE/BDTI` is available on free tier before implementing; if unavailable, document fallback in collector's module docstring
- `NDAQ_API_KEY` loaded from env var; stored as export in `~/.zshrc` per security rules — do NOT add to `.env` or `.env.example`
- Store column: `value` (float, BDTI index level) — no `total_` prefix, no `_usd` suffix
- ArcticDB key: `BDTI_1D`
- Callable as `python -m data.collectors.bdti`
- No live HTTP calls in unit tests — mock `requests.get` returning fixture JSON

## Repo Touchpoints
- `data/collectors/bdti.py` — new
- `data/config.py` — add `nasdaq_data_link_api_key`
- `tests/unit/test_bdti_collector.py` — new

## Acceptance Criteria
- [ ] `data/collectors/bdti.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] `BDTI_1D` series writes successfully with `value` column and DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] `nasdaq_data_link_api_key` present in `data/config.py`
- [ ] `tests/unit/test_bdti_collector.py` passes with mocked `requests.get` (no live API calls in tests)
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires Nasdaq Data Link API key (free registration at https://data.nasdaq.com)
- Shares `macro` ArcticDB library with QWS-1002 through QWS-1007
- Enables: tanker-rate leading indicator for CL strategy regime conditioning
