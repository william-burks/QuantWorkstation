# Story — COT Collector

## ID
QWS-1001

## Status
READY

## Summary
Add a CFTC Disaggregated COT collector that downloads weekly positioning data and writes
per-symbol net position series into a new `cot` ArcticDB library. Feeds the Regime node
with real positioning context.

## Problem
Strategy regime tagging (QWS-0502) is currently driven by price-derived indicators only.
CFTC Commitments of Traders data provides direct insight into commercial vs. non-commercial
positioning — a canonical input for positioning regime signals. Without a collector, this
data stays off the research pipeline entirely.

## Goal
Download CFTC Disaggregated COT reports weekly, map CFTC market codes to our symbol
conventions, and store commercial net, non-commercial net, and open interest as weekly
time series in ArcticDB.

## Deliverable
- `data/collectors/cot.py` — COT collector module
- `cot` ArcticDB library; keys `{ROOT}_cot` (e.g. `ES_cot`, `CL_cot`)
- `cot_symbols: list[str]` config field in `data/config.py`
- Weekly collection job registered in `execution/scheduler.py`
- Unit tests in `tests/unit/test_cot_collector.py`

## In Scope
- Download CFTC Disaggregated COT bulk CSV (no API key required; public URL)
- Parse columns: commercial net, non-commercial net, open interest
- CFTC market code → symbol mapping for: ES/MES, NQ/MNQ, GC/MGC, CL, ZN, ZB, 6E
- Write weekly series via `store.write_bars()` into `cot` library
- Idempotent write (re-download overwrites; no duplicate rows)
- Scheduler: weekly job (Friday after 15:30 ET when CFTC releases)

## Out of Scope
- Legacy COT (non-disaggregated) report parsing
- Intraweek interpolation of COT data
- Graph ingestion / Regime node updates (separate story if needed)
- Backfill beyond what CFTC bulk download provides (~3 years)

## Implementation Notes
- CFTC bulk download URL: `https://www.cftc.gov/files/dea/history/fut_disagg_txt_hist_2006_2016.zip`
  and current-year file; check `https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  for exact URLs — verify before implementing
- `fredapi` not needed — pure CSV download via `requests` or `urllib`
- Store columns: `comm_net`, `noncomm_net`, `open_interest` (no `total_` prefix, no `_usd` suffix)
- Weekly data: index on report date (Tuesday of report week, not release Friday)
- Symbol map lives in `cot.py` as a module-level dict `CFTC_SYMBOL_MAP`
- Follow same collector pattern as `ibkr_futures.py` — module-level `_CONTRACT_SPECS` analog

## Acceptance Criteria
- [ ] `data/collectors/cot.py` exists and is importable
- [ ] `cot` ArcticDB library is created on first run
- [ ] `ES_cot`, `CL_cot`, and at least 4 other symbols write successfully with correct columns
- [ ] Re-running collector is idempotent (no duplicate rows, no crash)
- [ ] `cot_symbols` present in `data/config.py` with sensible default list
- [ ] Weekly scheduler job registered and callable without error
- [ ] `tests/unit/test_cot_collector.py` passes with mocked HTTP responses (no live download in tests)
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] Collector merged to main
- [ ] ArcticDB `cot` library seeded with at least 52 weeks of data for all configured symbols
- [ ] Scheduler job confirmed callable
- [ ] Unit tests green
- [ ] Story marked CLOSED

## Dependencies
- No blockers
- Enables: COT positioning as input to Regime tagging (future story)
- Enables: commercial/non-commercial divergence as strategy signal input
