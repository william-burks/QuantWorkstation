# Story — Data Quality Validation

## ID
QWS-1010

## Status
READY

## Date
2026-04-12

## Summary
Add a `data/validation.py` module (~100 lines, zero new dependencies) with runtime OHLCV
validation checks. Called inline by each collector before writing to ArcticDB. P1 checks
raise immediately; P2/P3 log warnings. Retrofit into existing collectors.

## Problem
Collectors write directly to ArcticDB without verifying data shape or integrity. Silent bad
data (NaN prices, duplicate timestamps, wrong timezone, OHLCV relationship violations) corrupts
strategy backtest results without any diagnostic signal. Bugs surface downstream as confusing
Sharpe values or unexplained PnL spikes, not as clear data errors.

## Goal
Catch bad data at the write boundary — not in backtest, not in research review. P1 violations
fail loud and abort the write. P2/P3 log warnings so Will can decide whether to proceed.

## Deliverable
- `data/validation.py` — runtime validation module, ~100 lines, zero new dependencies
- `alpaca_crypto.py` and `ibkr_futures.py` retrofitted to call `validate_bars` before `write_bars`
- Unit tests in `tests/unit/test_validation.py` using constructed DataFrames (no live data)

## In Scope

**`validate_bars(df: pd.DataFrame, freq: str) -> None`** — raises `ValueError` on P1; logs
`warnings.warn` on P2/P3. `freq` is a pandas offset string (e.g. `'1H'`, `'1D'`).

### P1 — Fail loud, raise immediately

| Check | Condition | Error message pattern |
|---|---|---|
| OHLCV high/low | `high >= low` for all rows | `"OHLCV violation: high < low at {timestamps}"` |
| Close in range | `low <= close <= high` for all rows | `"OHLCV violation: close out of [low, high] at {timestamps}"` |
| Open in range | `low <= open <= high` for all rows | `"OHLCV violation: open out of [low, high] at {timestamps}"` |
| No NaN prices | No NaN in `open`, `high`, `low`, `close` columns | `"NaN prices in {columns} at {timestamps}"` |
| No zero prices | No zero in `open`, `high`, `low`, `close` | `"Zero prices in {columns} at {timestamps}"` |
| No negative prices | No negative in `open`, `high`, `low`, `close` | `"Negative prices in {columns} at {timestamps}"` |
| Unique timestamps | No duplicate index entries | `"Duplicate timestamps: {timestamps}"` |
| UTC timezone | `df.index.tz == UTC` | `"Index timezone must be UTC, got {tz}"` |

### P2 — Warn, do not raise

| Check | Condition |
|---|---|
| Gap detection | Index diffs > 2× expected bar spacing (derived from `freq`). Log count of gaps and first occurrence. |

### P3 — Warn only

| Check | Condition |
|---|---|
| Row count vs expected | Row count < 95% of expected bars for the date range and `freq`. Log actual vs expected. |

## Out of Scope
- Great Expectations or any external validation library
- Separate daily validation pass — validation is inline only
- Volume column validation (not in scope; futures `volume` can be 0 legitimately)
- Schema migration or data repair — validation raises/warns; caller decides to abort or continue

## Implementation Notes
- `validate_bars` is the single public function; all checks internal helpers
- Import path: `from data.validation import validate_bars`
- Use `warnings.warn(..., stacklevel=2)` for P2/P3 so warning points to caller
- `freq` → expected timedelta: use `pd.tseries.frequencies.to_offset(freq).delta` or `pd.Timedelta(freq)`
- P1 error messages include first 3 offending timestamps max (avoid flooding logs with 10k rows)
- Retrofit pattern for existing collectors:
  ```python
  from data.validation import validate_bars
  # after fetch, before write:
  validate_bars(df, freq="1H")
  store.write_bars(lib, symbol, df)
  ```
- New collectors (Epic 10) include `validate_bars` from the start — no retrofit needed
- Unit tests: construct DataFrames with known violations; assert `ValueError` raised or warning logged

## Acceptance Criteria
- [ ] `data/validation.py` exists, is importable, exports `validate_bars`
- [ ] P1: `ValueError` raised with descriptive message for each of the 8 P1 conditions
- [ ] P1: clean DataFrame with valid `freq` passes without error or warning
- [ ] P2: `warnings.warn` issued when index gap > 2× expected spacing; no raise
- [ ] P3: `warnings.warn` issued when row count < 95% of expected; no raise
- [ ] `alpaca_crypto.py` calls `validate_bars` before `write_bars`
- [ ] `ibkr_futures.py` calls `validate_bars` before `write_bars`
- [ ] Unit tests in `tests/unit/test_validation.py` cover all P1 conditions, P2 gap trigger, P3 undercount trigger, and clean-pass case
- [ ] No new pip dependencies introduced
- [ ] `ruff check` and `mypy --strict` clean

## Definition of Done
- [ ] `data/validation.py` merged to main
- [ ] Both existing collectors retrofitted and confirmed not broken by retrofit (unit tests still green)
- [ ] All `test_validation.py` tests green
- [ ] Manual spot check: introduce a NaN into a test DataFrame, confirm `ValueError` raised
- [ ] Story marked CLOSED

## Dependencies
- **No hard blockers**
- Soft dependency on QWS-1001: `write_series` path in new collectors should also call `validate_bars` — coordinate at implementation time
- Enables: reliable data foundation for all Epic 10 collectors
- Enables: clean error signal when backtest results look anomalous
