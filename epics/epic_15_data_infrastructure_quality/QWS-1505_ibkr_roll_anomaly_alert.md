# Story — IBKR Roll Anomaly Alert

## ID
QWS-1505

## Status
PLANNED

## Type
code

## Blocked On
QWS-1503

## Summary
Raise `RollAnomalyError` in `_ratio_stitch()` when an individual roll ratio falls outside `[roll_anomaly_min, roll_anomaly_max]` to block silent corruption of stitched futures series.

## Problem
`_ratio_stitch()` logs roll ratios but silently applies any value. A bad contract fetch (IBKR returns partial data for an expired contract) can produce a ratio of 0.1 or 10.0, which corrupts the entire stitched series.

## Goal
Individual roll ratios outside configured bounds raise `RollAnomalyError` with full context; Prefect flow marks FAILED; fallback path logs WARNING but does not raise.

## Design
- Guard applies to the **individual roll ratio** (`ratio = p_new / p_old`), NOT the cumulative ratio — the cumulative can legitimately be large from compounding
- `_ratio_stitch()` uses an endpoint fallback path when no overlap exists between contracts. On the fallback path, the ratio may look extreme due to contango/backwardation, not a data error. Log a prominent `WARNING` on the fallback path but do NOT raise `RollAnomalyError`
- `RollAnomalyError(ValueError)` defined in `data/validation.py` alongside `SchemaError`
- Bounds: `roll_anomaly_min: float = 0.80` and `roll_anomaly_max: float = 1.20` in `data/config.py` `Settings`
- `RollAnomalyError` propagates through `_seed_stitched()` → `collect()` → caught by `collect_all()` `log.exception()` → Prefect flow marks task FAILED

## In Scope
- `data/collectors/ibkr_futures.py` — add bounds check in `_ratio_stitch()` for individual roll ratio; add fallback path WARNING
- `data/validation.py` — add `class RollAnomalyError(ValueError): pass`
- `data/config.py` — add `roll_anomaly_min: float = 0.80` and `roll_anomaly_max: float = 1.20` to `Settings`

## Repo Touchpoints
- `data/collectors/ibkr_futures.py` — in `_ratio_stitch()`: check individual roll ratio against `[Settings.roll_anomaly_min, Settings.roll_anomaly_max]`; raise `RollAnomalyError(roll_ts, p_old_contract, p_new_contract, ratio)` if outside bounds; fallback path logs `WARNING "Roll fallback path — no overlap; ratio may reflect contango/backwardation"` and does not raise
- `data/validation.py` — add `class RollAnomalyError(ValueError): pass`
- `data/config.py` — add `roll_anomaly_min: float = 0.80`, `roll_anomaly_max: float = 1.20` to `Settings`

## Acceptance Criteria
- [ ] `RollAnomalyError` importable from `data/validation.py`
- [ ] Individual roll ratio outside `[roll_anomaly_min, roll_anomaly_max]` raises `RollAnomalyError` with full context (roll timestamp, p_old contract, p_new contract, computed ratio)
- [ ] Cumulative ratio is never checked — only per-roll ratio
- [ ] Fallback path logs WARNING, does not raise
- [ ] `RollAnomalyError` propagates up; `collect_all()` logs it; Prefect flow marks FAILED
- [ ] Bounds read from `Settings`; defaults 0.80 / 1.20
- [ ] Test: synthetic frames with 25% individual roll gap → raises; 5% → logs ratio, continues; fallback path → WARNING logged, continues

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: RollAnomalyError importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.validation import RollAnomalyError; print('ok')"`
- expect_contains: "ok"

### AC2: individual roll ratio outside bounds raises with context
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_roll_anomaly.py -k "anomaly_raises" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: cumulative ratio not checked
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_roll_anomaly.py -k "cumulative_not_checked" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: fallback path logs WARNING, does not raise
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_roll_anomaly.py -k "fallback_warns" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC6: bounds from Settings defaults
- type: cli
- cmd: `source .venv/bin/activate && python -c "from data.config import Settings; s=Settings(); print(s.roll_anomaly_min, s.roll_anomaly_max)"`
- expect_contains: "0.8"
- expect_contains: "1.2"

### AC7: synthetic test cases
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_ibkr_roll_anomaly.py -v 2>&1 | tail -10`
- expect_contains: "passed"
