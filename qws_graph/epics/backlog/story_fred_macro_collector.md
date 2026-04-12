# Story — FRED Macro Collector

## ID
QWS-1002

## Status
READY

## Summary
Add a FRED macro collector that pulls key daily macro series (yield curve, credit spreads,
VIX) via the `fredapi` Python package and writes them into a new `macro` ArcticDB library.
Provides macro regime context for strategy research.

## Problem
Research currently has no systematic access to macro regime context — yield curve shape,
credit stress, and vol regime. These are standard regime inputs missing from the pipeline.
Without them, Regime tagging (QWS-0502) is limited to price-derived signals and cannot
distinguish macro-driven from momentum-driven regimes.

## Goal
Collect 5 key FRED series daily, write into ArcticDB `macro` library, and register a
daily scheduler job. No graph changes required — this is pure data infrastructure.

## Deliverable
- `data/collectors/fred.py` — FRED collector module
- `macro` ArcticDB library; keys `{SERIES_ID}_1D` (e.g. `DGS10_1D`, `T10Y2Y_1D`)
- `fred_api_key: str` and `fred_series: list[str]` config fields in `data/config.py`
- Daily collection job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_fred_collector.py`

## In Scope
Series to collect (initial set):
| Series ID | Description |
|---|---|
| `DGS2` | 2-year Treasury yield |
| `DGS10` | 10-year Treasury yield |
| `T10Y2Y` | 10Y–2Y yield spread (pre-computed by FRED) |
| `VIXCLS` | CBOE VIX close |
| `BAMLH0A0HYM2` | ICE BofA High Yield OAS |

- Fetch via `fredapi.Fred` client
- Write daily series via `store.write_bars()` into `macro` library
- Idempotent: incremental fetch from last stored date; no full re-pull on every run
- Scheduler: daily job (after 18:00 ET when FRED updates)

## Out of Scope
- Non-daily series (weekly, monthly) — defer to a follow-on story if needed
- Derived features or cross-series calculations (e.g. curve slope logic)
- Graph ingestion / Regime node updates (separate story)
- Backfill beyond FRED API max history on first seed

## Implementation Notes
- `fredapi` pip package: `pip install fredapi`; add to `pyproject.toml` dependencies
- `fred_api_key` loaded from env var `FRED_API_KEY` (add to `.env.example`, not `.env`)
- Store column name: `value` for each series (single-column series; no OHLCV)
- Library key pattern: `{SERIES_ID}_1D` — lowercase series ID not required; match FRED ID exactly
- Incremental fetch: read last stored date via `store.read_bars()`, pass `observation_start` to FRED
- Follow same collector pattern as `alpaca_crypto.py` — module callable as `python -m data.collectors.fred`
- No live FRED calls in unit tests — mock `fredapi.Fred` client

## Acceptance Criteria
- [ ] `data/collectors/fred.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run
- [ ] All 5 series write successfully with correct `value` column and DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] `fred_api_key` and `fred_series` present in `data/config.py`
- [ ] `FRED_API_KEY` documented in `.env.example`
- [ ] Daily scheduler job registered and callable without error
- [ ] `tests/unit/test_fred_collector.py` passes with mocked `fredapi` client
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded with all 5 series (full available history)
- [ ] Incremental run confirmed: second run appends 0 rows, no crash
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- No blockers
- Requires FRED API key (free registration at https://fred.stlouisfed.org/docs/api/api_key.html)
- Enables: yield curve / credit / vol regime context for strategy research
- Enables: macro-conditioned regime tagging (future story)
