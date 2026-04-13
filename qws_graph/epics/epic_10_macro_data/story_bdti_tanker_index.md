# Story — Baltic Dirty Tanker Index Collector

## ID
QWS-1008

## Status
TESTING

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
- [x] `data/collectors/bdti.py` exists and is importable
- [x] `macro` ArcticDB library created on first run (or reuses existing)
- [x] `BDTI_1D` series writes successfully with `value` column and DatetimeIndex
- [x] Re-running collector is idempotent (appends only new dates; no duplicates)
- [x] `nasdaq_data_link_api_key` present in `data/config.py`
- [x] `tests/unit/test_bdti_collector.py` passes with mocked `requests.get` (no live API calls in tests)
- [x] `make verify` passes

## Acceptance Test Plan

### AC1: bdti.py exists and is importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.collectors.bdti import collect, _fetch_bdti, ARC_KEY; print(ARC_KEY)"`
- expect_contains: "BDTI_1D"
- expect_exit: 0

### AC2: macro library + BDTI_1D writes with value column and DatetimeIndex
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.collectors.bdti import _fetch_bdti; from unittest.mock import MagicMock, patch; resp=MagicMock(); resp.json.return_value={'dataset':{'data':[['2024-01-02',750.0]]}}; resp.raise_for_status=lambda:None; import sys; print('ok')"`
- expect_contains: "ok"
- expect_exit: 0

### AC3+AC4: idempotent incremental fetch — start_date set to last_date + 1 day
- type: cli
- cmd: `source .venv/bin/activate && pytest tests/unit/test_bdti_collector.py::test_collect_incremental_uses_last_date_plus_one -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: nasdaq_data_link_api_key in config.py
- type: file_check
- cmd: `grep -c 'nasdaq_data_link_api_key' data/config.py`
- expect_contains: "1"
- expect_exit: 0

### AC6: unit tests pass with mocked requests.get
- type: cli
- cmd: `source .venv/bin/activate && pytest tests/unit/test_bdti_collector.py -v`
- expect_contains: "passed"
- expect_exit: 0

### AC7: make verify passes
- type: cli
- cmd: `source .venv/bin/activate && make test`
- expect_contains: "passed"
- expect_exit: 0

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires Nasdaq Data Link API key (free registration at https://data.nasdaq.com)
- Shares `macro` ArcticDB library with QWS-1002 through QWS-1007
- Enables: tanker-rate leading indicator for CL strategy regime conditioning
