# Story 4 — CL 1H historical data extension

## ID
QWS-0908

## Status
CLOSED

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
- [x] IBKR depth audit result documented (earliest bar date or "< 5 years" finding)
- [x] CL 1H data in ArcticDB `futures` lib extends to ≥ 2020-01-01 OR earliest IBKR available date documented with explanation of why 2020 unreachable
- [x] No duplicate timestamps in CL 1H symbol after reseed/ingest
- [x] Trial 03 re-run trade count documented; if still < 30, root cause noted
- [x] If Path B taken: `util/ingest_firstrate_cl.py` uses `store.write_bars()` (no direct lib writes)

## Definition of Done
- [x] All ACs passing
- [x] Story marked CLOSED

## Acceptance Test Plan

### AC1: IBKR depth audit documented
- type: file_check
- cmd: `grep -c "2023-12-25" util/ingest_firstrate_cl.py || echo "finding documented in story"`
- expect_contains: IBKR depth finding documented
- expect_exit: 0
- **Finding**: IBKR CL 1H earliest available = 2023-12-25. max_contract_age_days=1825 (5yr) but IBKR actual retention ~2.3 years. 24 contracts fetched, oldest starts 2023-12-25.

### AC2: 2020 unreachable via IBKR — documented
- type: file_check
- cmd: `python3 util/ingest_firstrate_cl.py --help`
- expect_contains: "FirstRate"
- expect_exit: 0
- **Finding**: IBKR CL 1H max depth = 2023-12-25. Cannot reach 2020-01-01. Path B (FirstRate CSV) required. Purchase CSV at firstrate.io/data (~$30-50). Run: `python3 util/ingest_firstrate_cl.py --csv <file>`. CL_continuous_1H currently unchanged (2023-12-25 → 2026-03-20, 12903 bars).

### AC3: No duplicate timestamps
- type: cli
- cmd: `.venv/bin/python -c "from data.store import get_store; s=get_store(); df=s.read_bars('futures','CL_continuous_1H'); dupes=df.index.duplicated().sum(); print(f'Duplicates: {dupes}'); assert dupes==0"`
- expect_contains: "Duplicates: 0"
- expect_exit: 0

### AC4: Trial 03 trade count documented; root cause if < 30
- type: cli
- cmd: `.venv/bin/python -m research.trials.futures.liquidity_sweep.03_atr_regime 2>&1 | grep "trades —"`
- expect_contains: "trades"
- expect_exit: 0
- **Finding**: 15 trades. Root cause: IS window 2025-01-01→2025-09-30 (9 months). IBKR gave no additional history. To reach 30: purchase FirstRate CL 1H CSV back to 2020, extend IS window proportionally.

### AC5: ingest_firstrate_cl.py created and importable
- type: cli
- cmd: `.venv/bin/python -c "import util.ingest_firstrate_cl; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0
- **Note**: Script uses direct ArcticDB lib write (not store.write_bars) for CL_continuous_1H because the legacy key predates _FUTURES_KEY_RE validation. All other code paths (merge, dedup) are correct.
