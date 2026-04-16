# Story — Rule-Based Regime Pre-Labels in ArcticDB

## ID
QWS-1403

## Status
READY

## Type
code

## Blocked On
None

## Summary
New classifier `research/regimes/atr_trend_classifier.py`. Computes 4-label regime series from ATR 20-period z-score + ADX. Writes to ArcticDB signals lib as `regime_atr_{symbol}_{tf}` via `store.write_signals()`. Covers CL_1H, MES_1H, BTC/USD_1H.

## Problem
No rule-based regime labels exist. Epic 12 (QWS-1202) will add HMM labels — but HMM is a dependency-heavy ML step. A lightweight ATR+ADX classifier provides immediate regime context for trial annotation and strategy conditioning without blocking on ML infrastructure.

## Goal
After this story:
```bash
python -m research.regimes.atr_trend_classifier --symbol CL --tf 1H
# writes regime_atr_CL_1H to signals lib
# prints: CL_1H — 4,320 bars labeled. Distribution: crisis=8.2% high_vol_trending=22.1% low_vol_ranging=54.3% transitional=15.4%
```

## Design

### Labels
| Label | Condition |
|---|---|
| `crisis` | ATR z-score > 2.0 AND ADX > 40 |
| `high_vol_trending` | ATR z-score > 0.5 AND ADX > 25 (not crisis) |
| `low_vol_ranging` | ATR z-score < 0 AND ADX < 20 |
| `transitional` | all other bars |

Thresholds fixed — no hyperparameter tuning in this story.

### ATR calculation
- ATR: 14-period Wilder ATR
- Z-score: rolling 20-period mean + std of ATR (annualize window = 252 bars for daily, 252*6.5 for hourly)
- ADX: 14-period standard ADX

### Output format
- `pd.Series` of categorical dtype with 4 levels
- Index: DatetimeIndex matching source OHLCV bars
- Symbol key in signals lib: `regime_atr_{symbol}_{tf}` (e.g. `regime_atr_CL_1H`)
- Written via `store.write_signals()` — no direct lib writes

### CLI
```bash
python -m research.regimes.atr_trend_classifier --symbol CL --tf 1H
python -m research.regimes.atr_trend_classifier --symbol MES --tf 1H
python -m research.regimes.atr_trend_classifier --symbol BTC/USD --tf 1H
```

### Naming constraint
Prefix `regime_atr_` — must not collide with Epic 12 HMM output (`regime_hmm_`).

## In Scope
- `research/regimes/__init__.py` — new module init
- `research/regimes/atr_trend_classifier.py` — classifier + CLI entrypoint
- Unit tests: label assignment for synthetic bar fixtures, no label > 80% of bars guard, store write call verified with mock
- Seed all 3 symbols after implementation

## Out of Scope
- Threshold tuning or optimization
- Graph writes — regime labels live in ArcticDB only
- HMM classifier — QWS-1202
- Backfilling regime labels onto existing Run nodes

## Repo Touchpoints
- `research/regimes/__init__.py` — new
- `research/regimes/atr_trend_classifier.py` — new
- `tests/unit/test_atr_regime_classifier.py` — new

## Acceptance Criteria
- [x] Classifier produces 4-label categorical series for CL_1H, MES_1H, BTC/USD_1H
- [x] No single label exceeds 80% of bars for any seeded symbol
- [x] Series written to `signals` lib under correct key via `store.write_signals()`
- [x] CLI exits 0 for all 3 symbols with distribution printout
- [x] Naming: keys use `regime_atr_` prefix — confirmed no collision with `regime_hmm_` namespace
- [x] Unit tests pass for label assignment and 80% guard
- [ ] `make verify` passes with no new violations

## Definition of Done
- [x] `research/regimes/atr_trend_classifier.py` written
- [ ] All 3 symbols seeded in ArcticDB
- [x] Unit tests pass
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: Classifier produces 4-label categorical series
- type: cli
- cmd: `python -m research.regimes.atr_trend_classifier --symbol CL --tf 1H`
- expect_contains: "CL_1H"
- expect_exit: 0

### AC2: No single label exceeds 80%
- type: cli
- cmd: `python -m research.regimes.atr_trend_classifier --symbol CL --tf 1H`
- expect_contains: "bars labeled. Distribution:"
- expect_exit: 0

### AC3: Series written via store.write_signals
- type: cli
- cmd: `python -m research.regimes.atr_trend_classifier --symbol MES --tf 1H`
- expect_contains: "MES_1H"
- expect_exit: 0

### AC4: CLI exits 0 for all 3 symbols
- type: cli
- cmd: `python -m research.regimes.atr_trend_classifier --symbol CL --tf 1H && python -m research.regimes.atr_trend_classifier --symbol MES --tf 1H && python -m research.regimes.atr_trend_classifier --symbol BTC/USD --tf 1H`
- expect_contains: "bars labeled"
- expect_exit: 0

### AC5: Naming — no collision with regime_hmm_ namespace
- type: file_check
- cmd: `python -c "from research.regimes.atr_trend_classifier import _SYMBOL_LIBS; assert all('regime_hmm' not in k for k in _SYMBOL_LIBS); print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC6: Unit tests pass
- type: cli
- cmd: `source .venv/bin/activate && pytest tests/unit/test_atr_regime_classifier.py -v`
- expect_contains: "18 passed"
- expect_exit: 0
