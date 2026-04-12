# Story 4 — CL 1H historical data extension

## ID
QWS-0908

## Status
READY

## Type
infra

## Blocked On
None

## Summary
Extend CL 1H bar history to at least 2020-01-01 so regime-filtered ATR strategies can reach the 30-trade promotion gate.

## Problem
CL 1H data starts 2025-01-01 (~15 months). ATR-filtered CL sweep produces 16/30 trades across full available window — promotion gate permanently unreachable. Regime conditioning work stalled.

## Goal
CL 1H bars extend to ≥ 2020-01-01. Re-run of Trial 03 (ATR regime liquidity sweep) reaches 30-trade gate.

## Design
Two-path decision gated on IBKR depth audit:
- **Path A** — IBKR provides ≥ 5 years CL 1H: reseed via existing `util/reseed_symbol.py`. No new code.
- **Path B** — IBKR depth < 5 years: purchase FirstRate Data CL 1H CSV (~$30-50). Write `util/ingest_firstrate_cl.py` to normalize FirstRate CSV → `futures` ArcticDB lib via `store.write_bars()`. Stitch cleanly with existing bars (no duplicate timestamps, ascending time index).

## In Scope
1. Audit IBKR historical depth for CL 1H — run `data/collectors/ibkr_futures.py` in audit mode; report earliest available bar date
2. Path A: reseed via `util/reseed_symbol.py`; document new IS window start date
3. Path B (if needed): `util/ingest_firstrate_cl.py` — normalize FirstRate CSV format, write via `store.write_bars()`, stitch with existing bars
4. Re-run Trial 03 (`research/trials/futures/liquidity_sweep/`) after data extension; verify trade count increases

## Out of Scope
- No other instruments (CL 1H only)
- No change to promotion gate threshold
- No automated data pipeline — one-time backfill only

## Repo Touchpoints
<!-- MAX 5 FILES. If you need more, split the story. -->
- `data/collectors/ibkr_futures.py` — audit mode run (read only)
- `util/reseed_symbol.py` — Path A execution (existing script)
- `util/ingest_firstrate_cl.py` — Path B new ingest script
- `research/trials/futures/liquidity_sweep/` — re-run Trial 03 to verify

## Acceptance Criteria
- [ ] IBKR depth audit result documented (earliest bar date or "< 5 years" finding)
- [ ] CL 1H data in ArcticDB `futures` lib extends to ≥ 2020-01-01 OR earliest IBKR available date documented with explanation of why 2020 unreachable
- [ ] No duplicate timestamps in CL 1H symbol after reseed/ingest
- [ ] Trial 03 re-run trade count documented; if still < 30, root cause noted
- [ ] If Path B taken: `util/ingest_firstrate_cl.py` uses `store.write_bars()` (no direct lib writes)

## Definition of Done
- [ ] All ACs passing
- [ ] Story marked CLOSED
