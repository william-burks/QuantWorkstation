# Story — Vendor Schema Contract: Alpaca

## ID
QWS-1502

## Status
DEFERRED

## Type
code

## Blocked On
None

> **Deferred 2026-04-25 — crypto is post-MVP market. Futures-first strategy means Alpaca schema validation is not on the critical path. Fully spec'd for when crypto re-enters scope.**

## Summary
Add `_validate_vendor_schema()` to `alpaca_crypto.py` to catch Alpaca API schema changes before bad bars enter ArcticDB.

## Problem
Alpaca has changed the Bar object between API versions. Alpaca Bar objects are Pydantic models — missing fields won't raise `AttributeError`, they'll silently be `None`. Schema drift silently writes bad data or fails mid-collection with a cryptic error.

## Goal
Any Alpaca Bar with a None or missing required field raises `SchemaError` with a field diff before ArcticDB write. Unknown extra fields log WARNING and do not block.

## Design
- Validator checks required fields via `getattr(bar, field, None) is None` — not `hasattr()` alone, because Pydantic always has the attribute
- `volume` is not in `validate_bars()` `_REQUIRED_COLS` — the vendor schema contract is the right place to enforce its presence from Alpaca
- `SchemaError(ValueError)` defined in `data/validation.py` — do not reuse bare `ValueError`
- Validator fires only on non-empty bar lists (`if not raw_bars: return`)
- `collect_all()` already catches `Exception` broadly — `SchemaError` propagates up from `collect()`, caught by `collect_all()`, logs and continues to next symbol

## In Scope
- `data/collectors/alpaca_crypto.py` — new `_validate_vendor_schema(raw_bars: list) -> None` called before `_bars_to_df()`
- `data/validation.py` — new `class SchemaError(ValueError): pass`

## Repo Touchpoints
- `data/collectors/alpaca_crypto.py` — add `_validate_vendor_schema(raw_bars: list) -> None` before `_bars_to_df()`; pinned required fields: `open`, `high`, `low`, `close`, `volume`, `timestamp`
- `data/validation.py` — add `class SchemaError(ValueError): pass`

## Acceptance Criteria
- [ ] `SchemaError` importable from `data/validation.py`
- [ ] Any Alpaca Bar with a None or missing required field raises `SchemaError` with diff before ArcticDB write
- [ ] Unknown extra fields log `WARNING`, do not raise
- [ ] On `SchemaError`: collector logs the field diff, continues to next symbol, does NOT write partial data to ArcticDB
- [ ] Validator skips empty bar lists silently
- [ ] Unit test: mock Bar with `volume=None` → `SchemaError` raised; fully valid Bar → passes

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: SchemaError importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.validation import SchemaError; print('ok')"`
- expect_contains: "ok"

### AC2: missing required field raises SchemaError
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_alpaca_schema_contract.py -k "missing_required" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: unknown extra fields log WARNING, do not raise
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_alpaca_schema_contract.py -k "extra_fields" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: SchemaError → log + continue, no partial write
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_alpaca_schema_contract.py -k "schema_error_no_write" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC5: empty bar list skipped silently
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_alpaca_schema_contract.py -k "empty_bars" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC6: unit test mock Bar volume=None
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_alpaca_schema_contract.py -v 2>&1 | tail -5`
- expect_contains: "passed"
