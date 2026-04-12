# Story — COT Collector

## ID
QWS-1001

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1000

## Summary
Add a CFTC Disaggregated COT collector that downloads weekly positioning data and writes per-symbol net position series into a new `cot` ArcticDB library via `write_series()`. Feeds the Regime node with real positioning context.

## Problem
Strategy regime tagging (QWS-0502) is currently driven by price-derived indicators only. CFTC Commitments of Traders data provides direct insight into commercial vs. non-commercial positioning — a canonical input for positioning regime signals. Without a collector, this data stays off the research pipeline entirely.

## Goal
Download CFTC Disaggregated COT reports weekly, map CFTC market codes to our symbol conventions, and store commercial net, non-commercial net, and open interest as weekly time series in ArcticDB via `write_series()`.

## In Scope
- Download CFTC Disaggregated COT bulk CSV (no API key required; public URL)
- Parse columns: commercial net, non-commercial net, open interest
- CFTC market code → symbol mapping for: ES/MES, NQ/MNQ, GC/MGC, CL, ZN, ZB, 6E
- Write weekly series via `store.write_series()` into `cot` library (not `write_bars()` — COT data is multi-column non-OHLCV)
- Idempotent write (re-download overwrites; no duplicate rows)

## Out of Scope
- Legacy COT (non-disaggregated) report parsing
- Intraweek interpolation of COT data
- Graph ingestion / Regime node updates (separate story)
- Backfill beyond what CFTC bulk download provides (~3 years)
- Scheduler job registration (handled by QWS-1100b)

## Implementation Notes
- CFTC bulk download URL: `https://www.cftc.gov/files/dea/history/fut_disagg_txt_hist_2006_2016.zip`
  and current-year file; check `https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  for exact URLs — verify before implementing
- `fredapi` not needed — pure CSV download via `requests` or `urllib`
- Store columns: `comm_net`, `noncomm_net`, `open_interest` (no `total_` prefix, no `_usd` suffix)
- Weekly data: index on report date (Tuesday of report week, not release Friday)
- Symbol map lives in `cot.py` as a module-level dict `CFTC_SYMBOL_MAP`
- Follow same collector pattern as `ibkr_futures.py` — module-level `_CONTRACT_SPECS` analog

## Repo Touchpoints
- `data/collectors/cot.py` — new
- `data/config.py` — add `cot_symbols`
- `tests/unit/test_cot_collector.py` — new

## Acceptance Criteria
- [ ] `data/collectors/cot.py` exists and is importable
- [ ] `cot` ArcticDB library is created on first run
- [ ] `ES_cot`, `CL_cot`, and at least 4 other symbols write successfully with correct columns (`comm_net`, `noncomm_net`, `open_interest`)
- [ ] `write_series()` used for COT data (not `write_bars()`)
- [ ] Re-running collector is idempotent (no duplicate rows, no crash)
- [ ] `cot_symbols` present in `data/config.py` with sensible default list
- [ ] `tests/unit/test_cot_collector.py` passes with mocked HTTP responses (no live download in tests)
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED

## Dependencies
- Enables: COT positioning as input to Regime tagging (future story)
- Enables: commercial/non-commercial divergence as strategy signal input
