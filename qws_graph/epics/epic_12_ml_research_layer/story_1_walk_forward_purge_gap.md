# Story 1 — Walk-forward Purge Gap

## ID
QWS-1201

## Status
READY

## Blocked On
None

## Summary
Add `purge_bars: int = 0` parameter to `walk_forward.py`. When > 0, drops N bars between
train end and test start on each fold. Prevents rolling feature leakage from multi-bar
lookback windows crossing the train/test boundary. Required for all ML trials. Default `0`
is a no-op — existing rule-based walk-forward behavior unchanged.

## Problem
Current `walk_forward.py` splits folds at a clean timestamp boundary with no gap. For
rule-based strategies this is fine — signals are stateless at bar T. For ML strategies with
rolling features (e.g. 20-bar RSI, 5-day return), the feature at bar T looks back into the
training window, causing data leakage. Without a purge gap, IS/OOS Sharpe comparisons
overstate OOS performance.

## Goal

```python
# Existing call — unchanged behavior
results = walk_forward(strategy, data, n_folds=5)

# ML call — drops 20 bars between train end and test start each fold
results = walk_forward(strategy, data, n_folds=5, purge_bars=20)
```

The purge bars are dropped from the test set only. Training set is unaffected. Per-fold
output includes `purge_bars` as a logged field so results are reproducible.

## Schema Extension
None — no graph changes.

## Design

### Parameter addition
`walk_forward.py` signature change:
```python
def walk_forward(
    strategy,
    data: pd.DataFrame,
    n_folds: int = 5,
    purge_bars: int = 0,      # NEW — default preserves existing behavior
    ...
) -> pd.DataFrame:
```

### Fold construction
For each fold `(train_end_idx, test_start_idx, test_end_idx)`:
- Current: `test_start_idx = train_end_idx + 1`
- With purge: `test_start_idx = train_end_idx + 1 + purge_bars`

If `purge_bars` would consume the entire test window, raise `ValueError` with a clear
message including fold index and bar counts.

### Output
Per-fold results CSV gains column `purge_bars_used` (int). Existing columns unchanged.

## In Scope
- `research/experiments/walk_forward.py` — add `purge_bars` parameter, fold boundary logic,
  ValueError guard
- Unit tests: purge_bars=0 matches existing behavior; purge_bars=N drops correct bars;
  oversized purge raises ValueError with descriptive message; per-fold output includes
  `purge_bars_used`

## Out of Scope
- ML walk-forward harness (`ml_walk_forward.py`) — separate story (QWS-1204)
- Backfilling purge gap on existing completed walk-forward results
- Purge logic for expanding-window (anchored) walk-forward variants

## Repo Touchpoints
- `research/experiments/walk_forward.py`
- `tests/unit/test_walk_forward_purge.py` — new

## Acceptance Criteria
- [ ] `walk_forward(..., purge_bars=0)` produces identical output to current behavior
  (verified by running existing walk-forward tests unchanged).
- [ ] `walk_forward(..., purge_bars=N)` drops exactly N bars at the start of each test
  window; train window is unaffected.
- [ ] Per-fold output CSV includes `purge_bars_used` column with the applied value.
- [ ] Calling with `purge_bars` large enough to eliminate all test bars raises `ValueError`
  with message including fold index, test window size, and purge_bars value.
- [ ] Unit tests cover: purge_bars=0, purge_bars=positive, oversized purge.
- [ ] `make verify` passes with no new violations.

## Definition of Done
- [ ] `walk_forward.py` updated with `purge_bars` parameter.
- [ ] Existing walk-forward tests pass unchanged.
- [ ] New unit tests pass.
- [ ] Story marked CLOSED.
