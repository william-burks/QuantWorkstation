# Story 4 — ML Walk-forward Harness

## ID
QWS-1204

## Status
PLANNED

## Blocked On
QWS-1203 (feature_builder — harness consumes feature DataFrames)

## Summary
New `research/experiments/ml_walk_forward.py` — ML analogue of `walk_forward.py`. Optuna
inner loop per fold for hyperparameter tuning. Per-fold: feature selection (top-N by
importance), model fit, OOS predict. Model artifacts serialized per fold. Output CSV
matches existing sweep output format → feeds `qw record --bundle` unchanged. Overfitting
guards baked in — IS/OOS gap flag, fold stability stdev, parameter/trade ratio.

## Key ACs
- `purge_bars` parameter wired through from QWS-1201 — required for ML calls (no default
  bypass allowed when using rolling features).
- N ≥ 3 folds enforced; ValueError if fewer requested.
- Per-fold overfitting checks:
  - `n_parameters / n_trades < 0.05` — flag `PARAM_DENSE` if violated
  - IS/OOS Sharpe ratio > 2.0 — flag `IS_OOS_GAP`
  - OOS trades < 60 — flag `INSUFFICIENT_SAMPLE`
- Fold stability: Sharpe stdev across folds logged in output CSV.
- Output CSV includes all existing sweep columns plus: `fold`, `purge_bars_used`,
  `n_parameters`, `n_trades_oos`, `is_oos_sharpe_ratio`, `fold_stability_stdev`,
  `overfit_flags` (comma-separated flag names, empty string if clean).
- Model artifacts: `research/models/<experiment_id>/fold_N.pkl` per fold.
- `qw record --bundle` accepts output CSV without modification.
- `ruff check` and `mypy --strict` pass.

## Dependencies
QWS-1205 (LightGBM signal model) consumes trained artifacts.
QWS-1206 (Results interpreter) reads output CSV + fold artifacts.

## Repo Touchpoints
- `research/experiments/ml_walk_forward.py` — new
- `tests/unit/test_ml_walk_forward.py` — new
- `tests/integration/test_ml_walk_forward_end_to_end.py` — new
