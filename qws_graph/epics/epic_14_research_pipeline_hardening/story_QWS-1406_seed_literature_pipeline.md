# Story — Seed Literature Pipeline

## ID
QWS-1406

## Status
READY

## Type
research

## Blocked On
None (pipeline built in Epic 26.4, commit 37daf27)

## Summary
Ingest ≥5 key academic papers into the literature pipeline. Pipeline already built — `qws_researcher/data/extracts/` is currently empty. No code changes needed.

## Problem
Literature search (`search_library()`) returns zero results. The pipeline exists but has no content. Research sessions have no paper-backed context for hypotheses.

## Goal
After this story:
```
search_library("mean reversion futures") → ≥2 hits
search_library("regime switching") → ≥2 hits
```

## Target Papers

| # | Paper | Authors | Topic |
|---|---|---|---|
| 1 | Returns to Buying Winners and Selling Losers (1993) | Jegadeesh & Titman | Momentum |
| 2 | Mean Reversion in Stock Prices (1988) | Poterba & Summers | Mean reversion |
| 3 | How Do Regimes Affect Asset Allocation (2004) | Ang & Bekaert | Regime switching |
| 4 | A New Approach to the Economic Analysis of Time Series (1989) | Hamilton | Regime switching / HMM |
| 5 | Momentum and Mean Reversion in Commodity Futures (2015) | Baltas & Kosowski | Momentum/MR futures |
| 6+ | 1-2 recent (2020+) papers on macro-conditioned futures strategies | — | Macro conditioning |

## Process
1. Download PDFs to `qws_researcher/inbox/` (or configured inbox path)
2. Run: `python qws_researcher/ingest_library.py` for each paper
3. Verify extracts written to `qws_researcher/data/extracts/`
4. Verify search returns hits

## Acceptance Criteria
- [ ] ≥5 papers ingested (verified by count in `data/extracts/`)
- [ ] `search_library("mean reversion futures")` returns ≥2 hits
- [ ] `search_library("regime switching")` returns ≥2 hits
- [ ] No code changes committed (ingestion work only)

## Definition of Done
- [ ] ≥5 papers ingested and searchable
- [ ] Search acceptance criteria verified
- [ ] Story marked CLOSED
