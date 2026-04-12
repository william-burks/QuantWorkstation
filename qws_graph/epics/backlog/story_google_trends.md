# Story — Google Trends Collector

## ID
QWS-1007

## Status
READY

## Summary
Add a Google Trends collector using the `pytrends` library that pulls weekly retail interest
scores (0–100) for gold and macro sentiment search terms and writes them into the shared
`macro` ArcticDB library. Provides a retail sentiment leading indicator for GC, MGC, and
BTC/USD strategies.

## Problem
Gold and crypto strategies have no structured view of retail search demand. Google Trends
weekly interest in terms like "buy gold", "gold inflation hedge", and "recession" leads
price moves by 1–3 weeks as retail participants discover a thesis before acting on it.
Without a collector, this sentiment surface is absent from the research pipeline.

## Goal
Collect weekly Google Trends interest scores for a configurable list of terms via `pytrends`,
write as weekly time series into ArcticDB `macro` library, and handle Google's unofficial
rate limits gracefully.

## Deliverable
- `data/collectors/google_trends.py` — Google Trends collector module — **new**
- `macro` ArcticDB library; keys per pattern `GTRENDS_{SLUG}`
  (e.g. `GTRENDS_BUY_GOLD`, `GTRENDS_GOLD_INFLATION_HEDGE`, `GTRENDS_RECESSION`, `GTRENDS_INFLATION`)
- `gtrends_terms: list[str]` config field in `data/config.py`
- Weekly scheduler job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_google_trends_collector.py`

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
- Real-time or daily Google Trends data (weekly resolution only for multi-year history)
- Geographic breakdown (global aggregate only)
- Trending searches or related queries
- Graph ingestion / Regime node updates (separate story)

## Implementation Notes
- `pytrends` is an unofficial library that scrapes Google Trends — it is best-effort;
  Google may block requests or change the API without notice. Treat all data as best-effort.
  If `pytrends` breaks, collector fails gracefully (logs error, exits 0 — does not crash scheduler)
- Install: `pip install pytrends` — add to `pyproject.toml` optional `macro` group
- No API key required; no credentials; `pytrends` uses anonymous sessions
- Slug construction for ArcticDB key: uppercase, replace spaces with underscores, strip punctuation
  (e.g. `"buy gold"` → `GTRENDS_BUY_GOLD`)
- Store column: `interest` (int, 0–100 Google score) — no `total_` prefix, no `_usd` suffix
- Weekly index on Monday of the reported week (pytrends returns ISO week start)
- Collector callable as `python -m data.collectors.google_trends`
- Unit tests must mock `pytrends.TrendReq` — no real HTTP in tests

## Acceptance Criteria
- [ ] `data/collectors/google_trends.py` exists and is importable
- [ ] `macro` ArcticDB library created on first run (or reuses existing)
- [ ] All 4 default terms write successfully with `interest` column and DatetimeIndex
- [ ] 60s sleep between term requests is present in production code path
- [ ] 429/500 retry logic present: one retry after 120s sleep; graceful skip on second failure
- [ ] Upsert behavior: re-running overwrites existing rows cleanly (no duplicate index)
- [ ] `gtrends_terms` present in `data/config.py` with default list of 4 terms
- [ ] Weekly scheduler job registered and callable without error
- [ ] `tests/unit/test_google_trends_collector.py` passes with mocked `pytrends.TrendReq` (no live requests)
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `macro` library seeded with all 4 Google Trends series (~5 years weekly)
- [ ] Incremental (upsert) run confirmed: second run completes without error, no duplicate rows
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- Blocked on QWS-1001 (COT Collector) — `write_series` / `read_series` store methods land there
- No API key required; `pytrends` library required in `pyproject.toml`
- Shares `macro` ArcticDB library with QWS-1002 through QWS-1006
- Note: pytrends is unofficial — if library breaks post-merge, treat as best-effort data; do not block other stories on its fix
- Enables: retail sentiment leading indicator for GC, MGC, BTC/USD strategy conditioning
