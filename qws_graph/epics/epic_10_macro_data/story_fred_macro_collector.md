# Story — FRED Macro Collector

## ID
QWS-1002

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1000

## Summary
Add a FRED macro collector that pulls key daily macro series (yield curve, credit spreads, VIX) via the `fredapi` Python package and writes them into a new `macro` ArcticDB library via `write_series()`. Provides macro regime context for strategy research.

## Problem
Research currently has no systematic access to macro regime context — yield curve shape, credit stress, and vol regime. These are standard regime inputs missing from the pipeline. Without them, Regime tagging (QWS-0502) is limited to price-derived signals and cannot distinguish macro-driven from momentum-driven regimes.

## Goal
Collect 5 key FRED series daily, write into ArcticDB `macro` library via `write_series()`. No graph changes required — this is pure data infrastructure.

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
- Write daily series via `store.write_series()` into `macro` library
- Idempotent: incremental fetch from last stored date; no full re-pull on every run

## Out of Scope
- Non-daily series (weekly, monthly)
- Derived features or cross-series calculations
- Graph ingestion / Regime node updates (separate story)
- Backfill beyond FRED API max history on first seed
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- `fredapi` pip package: add to `pyproject.toml` dependencies
- `fred_api_key` loaded from env var `FRED_API_KEY` (add to `.env.example`, not `.env`)
- Store column name: `value` for each series (single-column; no OHLCV)
- Library key pattern: `{SERIES_ID}_1D` — match FRED ID exactly
- Incremental fetch: read last stored date via `store.read_series()`, pass `observation_start` to FRED
- Callable as `python -m data.collectors.fred`
- No live FRED calls in unit tests — mock `fredapi.Fred` client

## Repo Touchpoints
- `data/collectors/fred.py` — new
- `data/config.py` — add `fred_api_key`, `fred_series`
- `tests/unit/test_fred_collector.py` — new

## Acceptance Criteria
- [ ] `data/collectors/fred.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run
- [ ] All 5 series write successfully with correct `value` column and DatetimeIndex
- [ ] Re-running collector is idempotent (appends only new dates; no duplicates)
- [ ] `fred_api_key` and `fred_series` present in `data/config.py`
- [ ] `FRED_API_KEY` documented in `.env.example`
- [ ] `tests/unit/test_fred_collector.py` passes with mocked `fredapi` client
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Requires FRED API key (free registration at https://fred.stlouisfed.org/docs/api/api_key.html)
- Enables: yield curve / credit / vol regime context for strategy research
- Enables: macro-conditioned regime tagging (future story)
