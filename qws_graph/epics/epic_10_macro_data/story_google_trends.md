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
- [ ] `data/collectors/google_trends.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] All 4 default terms write successfully with `interest` column and DatetimeIndex
- [ ] 60s sleep between term requests is present in production code path
- [ ] 429/500 retry logic present: one retry after 120s sleep; graceful skip on second failure
- [ ] Upsert behavior: re-running overwrites existing rows cleanly (no duplicate index)
- [ ] `gtrends_terms` present in `data/config.py` with default list of 4 terms
- [ ] `tests/unit/test_google_trends_collector.py` passes with mocked `pytrends.TrendReq` (no live requests)
- [ ] `make verify` passes

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- No API key required; `pytrends` library required in `pyproject.toml`
- Shares `macro` ArcticDB library with QWS-1002 through QWS-1006
- Note: pytrends is unofficial — if library breaks post-merge, treat as best-effort data; do not block other stories on its fix
- Enables: retail sentiment leading indicator for GC, MGC, BTC/USD strategy conditioning
