# Story — Data Quality Validation

## ID
QWS-1010

## Status
CLOSED

## Type
code

## Blocked On
None

## Summary
Add a `data/validation.py` module (~100 lines, zero new dependencies) with runtime OHLCV validation checks including stale feed detection and schema drift detection. Called inline by each collector before writing to ArcticDB. P1 checks raise immediately; P2/P3 log warnings. Retrofit into existing collectors.

## Problem
Collectors write directly to ArcticDB without verifying data shape or integrity. Silent bad data (NaN prices, duplicate timestamps, wrong timezone, OHLCV relationship violations, stale feeds, schema drift) corrupts strategy backtest results without any diagnostic signal. Bugs surface downstream as confusing Sharpe values or unexplained PnL spikes, not as clear data errors.

## Goal
Catch bad data at the write boundary — not in backtest, not in research review. P1 violations fail loud and abort the write. P2/P3 log warnings so the decision to proceed stays with the caller.

## In Scope

**`validate_bars(df: pd.DataFrame, freq: str) -> None`** — raises `ValueError` on P1; logs `warnings.warn` on P2/P3. `freq` is a pandas offset string (e.g. `'1H'`, `'1D'`).

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
| Stale feed check | Most recent index entry is > 3× expected bar spacing from now. Warn: `"Stale feed: last bar at {ts}, expected within {threshold}"` |
| Schema drift check | DataFrame columns don't include required columns for the declared `freq` type (`open/high/low/close` for bar data). Warn: `"Schema drift: missing columns {cols}"` |

### P3 — Warn only

| Check | Condition |
|---|---|
| Row count vs expected | Row count < 95% of expected bars for the date range and `freq`. Log actual vs expected. |

- `alpaca_crypto.py` and `ibkr_futures.py` retrofitted to call `validate_bars` before `write_bars`

## Out of Scope
- Great Expectations or any external validation library
- Separate daily validation pass — validation is inline only
- Volume column validation (futures `volume` can be 0 legitimately)
- Schema migration or data repair — validation raises/warns; caller decides to abort or continue

## Implementation Notes
- `validate_bars` is the single public function; all checks internal helpers
- Import path: `from data.validation import validate_bars`
- Use `warnings.warn(..., stacklevel=2)` for P2/P3 so warning points to caller
- `freq` → expected timedelta: use `pd.tseries.frequencies.to_offset(freq).delta` or `pd.Timedelta(freq)`
- P1 error messages include first 3 offending timestamps max
- Retrofit pattern for existing collectors:
  ```python
  from data.validation import validate_bars
  # after fetch, before write:
  validate_bars(df, freq="1H")
  store.write_bars(lib, symbol, df)
  ```
- New collectors (Epic 10) include `validate_bars` from the start — no retrofit needed

## Repo Touchpoints
- `data/validation.py` — new
- `data/collectors/alpaca_crypto.py` — retrofit
- `data/collectors/ibkr_futures.py` — retrofit
- `tests/unit/test_validation.py` — new

## Acceptance Criteria
- [x] `data/validation.py` exists, is importable, exports `validate_bars`
- [x] P1: `ValueError` raised with descriptive message for each of the 8 P1 conditions
- [x] P1: clean DataFrame with valid `freq` passes without error or warning
- [x] P2: `warnings.warn` issued when index gap > 2× expected spacing; no raise
- [x] P2: `warnings.warn` issued when most recent bar is > 3× expected spacing from now (stale feed check); no raise
- [x] P2: `warnings.warn` issued when required OHLCV columns are missing (schema drift check); no raise
- [x] P3: `warnings.warn` issued when row count < 95% of expected; no raise
- [x] `alpaca_crypto.py` calls `validate_bars` before `write_bars`
- [x] `ibkr_futures.py` calls `validate_bars` before `write_bars`
- [x] Unit tests in `tests/unit/test_validation.py` cover all P1 conditions, both P2 gap triggers, stale feed trigger, schema drift trigger, P3 undercount trigger, and clean-pass case
- [x] No new pip dependencies introduced
- [x] `make verify` passes

## Acceptance Test Plan

### AC1: validate_bars importable and exports correct symbol
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.validation import validate_bars; print('ok')"`
- expect_contains: "ok"
- expect_exit: 0

### AC2: P1 UTC timezone raises
- type: cli
- cmd: `source .venv/bin/activate && python -c "import pandas as pd; from data.validation import validate_bars; df = pd.DataFrame({'open':[100],'high':[101],'low':[99],'close':[100]}, index=pd.DatetimeIndex(['2024-01-01'])); validate_bars(df,'1H')" 2>&1`
- expect_contains: "timezone must be UTC"
- expect_exit: 1

### AC3: P1 high < low raises
- type: cli
- cmd: `source .venv/bin/activate && python -c "import pandas as pd; from data.validation import validate_bars; idx=pd.DatetimeIndex(['2024-01-01'],tz='UTC'); df=pd.DataFrame({'open':[100],'high':[99],'low':[101],'close':[100]},index=idx); validate_bars(df,'1H')" 2>&1`
- expect_contains: "high < low"
- expect_exit: 1

### AC4: P2 gap warns no raise
- type: cli
- cmd: `source .venv/bin/activate && python -c "import pandas as pd, warnings; from data.validation import validate_bars; idx=pd.date_range('2024-01-01',periods=5,freq='h',tz='UTC'); df=pd.DataFrame({'open':100,'high':101,'low':99,'close':100},index=idx); lst=list(idx); lst[2]=lst[1]+pd.Timedelta(hours=5); df.index=pd.DatetimeIndex(lst,tz='UTC'); warnings.filterwarnings('error','Stale feed'); warnings.filterwarnings('error','Row count'); validate_bars(df,'h'); print('no_raise')" 2>&1`
- expect_contains: "Gap detected"
- expect_exit: 0

### AC5: alpaca_crypto.py imports validate_bars
- type: file_check
- cmd: `grep -c 'from data.validation import validate_bars' data/collectors/alpaca_crypto.py`
- expect_contains: "1"
- expect_exit: 0

### AC6: ibkr_futures.py imports validate_bars
- type: file_check
- cmd: `grep -c 'from data.validation import validate_bars' data/collectors/ibkr_futures.py`
- expect_contains: "1"
- expect_exit: 0

### AC7: unit tests pass
- type: cli
- cmd: `source .venv/bin/activate && pytest tests/unit/test_validation.py -q 2>&1 | tail -3`
- expect_contains: "23 passed"
- expect_exit: 0

### AC8: no new pip dependencies
- type: file_check
- cmd: `grep -c 'great_expectations\|pandera\|cerberus' data/validation.py || echo "0"`
- expect_contains: "0"
- expect_exit: 0

### AC9: typecheck passes
- type: cli
- cmd: `make typecheck 2>&1 | tail -3`
- expect_contains: "Success"
- expect_exit: 0

## Definition of Done
- [x] All ACs passing
- [x] Tests green
- [x] Story marked CLOSED

## Dependencies
- No hard blockers
- Soft dependency on QWS-1000: `write_series` path in new collectors should also call `validate_bars` — coordinate at implementation time
- Enables: reliable data foundation for all Epic 10 collectors
- Enables: clean error signal when backtest results look anomalous
