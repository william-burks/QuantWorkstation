# Story — CONTFUT Revision Detection

## ID
QWS-1503

## Status
PLANNED

## Type
code

## Blocked On
None

## Summary
Detect when IBKR has silently re-adjusted historical CONTFUT prices and fix the `adjusted = False` metadata bug in `_bars_to_df()`.

## Problem
IBKR back-adjusts CONTFUT history on every new roll. Stored series silently diverges from a fresh fetch with no signal. Also: `adjusted = False` is currently written to bar metadata in `_bars_to_df()` for both CONTFUT and stitched FUT paths — this is factually wrong, as the data is ratio-adjusted.

## Goal
`adjusted` flag correctly reflects ratio-adjustment status for all call paths; revision check fires on CONTFUT collect even when incremental early-return would skip the fetch; warns (does not block) when close delta exceeds threshold.

## Design
**adjusted flag fix:**
`_bars_to_df()` at line 253 in `ibkr_futures.py` is shared by multiple call paths. Add `adjusted: bool = False` as a parameter:
- `_fetch_contfut()` calls `_bars_to_df()` → pass `adjusted=True`
- `_ratio_stitch()` returns the final stitched DataFrame → set `adjusted = True` on the result before returning
- `_fetch_contract_bars()` (individual contract fetches, pre-stitch) → continue using `adjusted=False`

**Revision detection:**
The CONTFUT incremental collect path has an early-return guard (`if last_bar >= now - timedelta(hours=1): return`). The revision comparison must run BEFORE this early-return check. Read stored data at the top of the CONTFUT branch regardless of the freshness check.

Comparison logic: `overlap = new_df.index.intersection(stored_df.index)` → compare `new_df.loc[overlap[0], 'close']` vs `stored_df.loc[overlap[0], 'close']`. Handle empty stored series (first seed) by skipping comparison and logging info. Also compare at last overlapping bar.

Threshold: `contfut_revision_threshold: float = 0.005` in `data/config.py` `Settings`.

## In Scope
- `data/collectors/ibkr_futures.py` — thread `adjusted: bool = False` through `_bars_to_df()` call chain; add revision check before early-return in CONTFUT branch
- `data/config.py` — add `contfut_revision_threshold: float = 0.005` to `Settings`

## Out of Scope
- Auto-reseed on revision detection
- Ratio ledger persistence

## Repo Touchpoints
- `data/collectors/ibkr_futures.py` — `_bars_to_df()` gains `adjusted: bool = False` param; `_fetch_contfut()` passes `adjusted=True`; `_ratio_stitch()` sets `adjusted=True` on result; CONTFUT collect reads stored data before early-return guard; computes overlap + compares close at first + last overlapping bar; warns if delta > threshold
- `data/config.py` — add `contfut_revision_threshold: float = 0.005` to `Settings`

## Acceptance Criteria
- [ ] `_bars_to_df()` accepts `adjusted: bool = False`; CONTFUT and stitched FUT paths pass `adjusted=True`; individual contract fetches pass `adjusted=False` (or rely on default)
- [ ] On CONTFUT collect, revision check fires even when incremental early-return would have skipped the fetch
- [ ] If no stored data (first seed): log `INFO "No stored CONTFUT data, skipping revision check"`, continue
- [ ] Warns (does not block, does not auto-reseed) if delta > threshold at first OR last overlapping bar
- [ ] Warning includes: symbol, fetch_date, stored_close, fetched_close, delta_pct, recommendation to full reseed
- [ ] Threshold read from `Settings.contfut_revision_threshold`; default 0.5%
- [ ] Test: synthetic DataFrames with 0.6% close delta at overlap → warns; 0.3% → logs only; empty stored → logs INFO, continues

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: adjusted flag threaded correctly
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_futures.py -k "adjusted_flag" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC2: revision check fires before early-return
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_futures.py -k "revision_check_before_early_return" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: empty stored → INFO log, continue
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_futures.py -k "empty_stored_contfut" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4+AC5: 0.6% delta warns with context fields
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_futures.py -k "revision_06pct_warns" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC6: threshold from Settings default 0.5%
- type: unit
- cmd: `source .venv/bin/activate && python -c "from data.config import Settings; s=Settings(); print(s.contfut_revision_threshold)"`
- expect_contains: "0.005"

### AC7: synthetic test cases
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_futures.py -k "contfut_revision" -v 2>&1 | tail -10`
- expect_contains: "passed"
