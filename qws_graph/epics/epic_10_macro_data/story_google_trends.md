# Story — Google Trends Collector

## ID
QWS-1007

## Status
READY

## Type
code

## Blocked On
None

## Summary
Add a Google Trends collector using the `pytrends` library that pulls weekly retail interest scores (0–100) for gold and macro sentiment search terms and writes them into the shared `macro` ArcticDB library via `write_series()`. Provides a retail sentiment leading indicator for GC, MGC, and BTC/USD strategies.

## Problem
Gold and crypto strategies have no structured view of retail search demand. Google Trends weekly interest in terms like "buy gold", "gold inflation hedge", and "recession" leads price moves by 1–3 weeks as retail participants discover a thesis before acting on it. Without a collector, this sentiment surface is absent from the research pipeline.

## Goal
Collect weekly Google Trends interest scores for a configurable list of terms via `pytrends`, write as weekly time series into ArcticDB `macro` library, and handle Google's unofficial rate limits gracefully.

## In Scope
Initial term list:
| Search Term | ArcticDB Key |
|---|---|
| `"buy gold"` | `GTRENDS_BUY_GOLD` |
| `"gold inflation hedge"` | `GTRENDS_GOLD_INFLATION_HEDGE` |
| `"recession"` | `GTRENDS_RECESSION` |
| `"inflation"` | `GTRENDS_INFLATION` |

- Fetch weekly interest scores via `pytrends` (`TrendReq.build_payload` with `timeframe` spanning last 5 years)
- Scores are relative (0–100 normalized to peak week within the pull window)
- One request per term with 60s sleep between terms to respect unofficial rate limits
- Retry logic: on `ResponseError` (HTTP 429 or 500), sleep 120s and retry once; if second attempt fails, log warning and skip that term for this run
- Write weekly series via `store.write_series()` into `macro` library
- Idempotent: pull full 5-year window on each run; upsert into ArcticDB (overwrite overlapping rows, append new)

## Out of Scope
- Real-time or daily Google Trends data (weekly resolution only)
- Geographic breakdown (global aggregate only)
- Trending searches or related queries
- Graph ingestion / Regime node updates (separate story)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- `pytrends` is an unofficial library — treat all data as best-effort; if library breaks, collector fails gracefully (logs error, exits 0)
- Install: `pip install pytrends` — add to `pyproject.toml` optional `macro` group
- No API key required; `pytrends` uses anonymous sessions
- Slug construction for ArcticDB key: uppercase, replace spaces with underscores, strip punctuation
- Store column: `interest` (int, 0–100 Google score) — no `total_` prefix, no `_usd` suffix
- Weekly index on Monday of the reported week (pytrends returns ISO week start)
- Callable as `python -m data.collectors.google_trends`
- Unit tests must mock `pytrends.TrendReq` — no real HTTP in tests

## Repo Touchpoints
- `data/collectors/google_trends.py` — new
- `data/config.py` — add `gtrends_terms`
- `tests/unit/test_google_trends_collector.py` — new

## Acceptance Criteria
- [x] `data/collectors/google_trends.py` exists and is importable
- [x] `macro` ArcticDB library created on first run (or reuses existing)
- [x] All 4 default terms write successfully with `interest` column and DatetimeIndex
- [x] 60s sleep between term requests is present in production code path
- [x] 429/500 retry logic present: one retry after 120s sleep; graceful skip on second failure
- [x] Upsert behavior: re-running overwrites existing rows cleanly (no duplicate index)
- [x] `gtrends_terms` present in `data/config.py` with default list of 4 terms
- [x] `tests/unit/test_google_trends_collector.py` passes with mocked `pytrends.TrendReq` (no live requests)
- [x] `make verify` passes

## Acceptance Test Plan

### AC1: google_trends.py exists and is importable
- type: cli
- cmd: `python -c "from data.collectors.google_trends import collect, DEFAULT_TERMS, _arc_key; print('ok')"`
- expect_contains: "ok"
- expect_exit: 0

### AC2: macro ArcticDB library created on first run
- type: cli
- cmd: `python -c "from data.store import get_store; s = get_store(); print(s.list_symbols('macro'))"`
- expect_contains: "[]"
- expect_exit: 0

### AC3: all 4 default terms write with interest column and DatetimeIndex
- type: cli
- cmd: `.venv/bin/pytest tests/unit/test_google_trends_collector.py::test_collect_written_df_has_interest_column_and_datetime_index -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: 60s sleep between term requests
- type: cli
- cmd: `.venv/bin/pytest tests/unit/test_google_trends_collector.py::test_collect_sleeps_between_terms -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: 429/500 retry logic
- type: cli
- cmd: `.venv/bin/pytest tests/unit/test_google_trends_collector.py::test_fetch_term_retries_on_response_error tests/unit/test_google_trends_collector.py::test_fetch_term_skips_on_double_response_error -v`
- expect_contains: "2 passed"
- expect_exit: 0

### AC6: upsert deduplicates index
- type: cli
- cmd: `.venv/bin/pytest tests/unit/test_google_trends_collector.py::test_collect_upsert_deduplicates_index -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC7: gtrends_terms in config.py
- type: cli
- cmd: `python -c "from data.config import Settings; s = Settings.model_fields; print('gtrends_terms' in s)"`
- expect_contains: "True"
- expect_exit: 0

### AC8: unit tests pass with mocked TrendReq
- type: cli
- cmd: `.venv/bin/pytest tests/unit/test_google_trends_collector.py -v`
- expect_contains: "18 passed"
- expect_exit: 0

### AC9: make verify passes (qws_graph unit tests)
- type: cli
- cmd: `make test`
- expect_contains: "passed"
- expect_exit: 0

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- No API key required; `pytrends` library required in `pyproject.toml`
- Shares `macro` ArcticDB library with QWS-1002 through QWS-1006
- Note: pytrends is unofficial — if library breaks post-merge, treat as best-effort data; do not block other stories on its fix
- Enables: retail sentiment leading indicator for GC, MGC, BTC/USD strategy conditioning
