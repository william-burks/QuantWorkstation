# Story 5 — LightGBM Signal Model

## ID
QWS-1205

## Status
PLANNED

## Blocked On
QWS-1204 (ML walk-forward harness — training and artifact serialization required before
inference strategy can load models)

## Summary
New `strategies/ml_signal_strategy.py` — subclass of `BaseStrategy`. `generate_signals()`
loads trained LightGBM model from artifact path, runs inference, returns {-1, 0, 1}. Same
`vectorbt_adapter.run()` path as rule-based strategies — no adapter changes. Training
delegated to `ml_walk_forward.py`. `Strategy.logic_type = "ml_model"`,
`model_class = "lightgbm"`.

## Key ACs
- `generate_signals()` loads model from `artifact_path` in Config; raises `FileNotFoundError`
  if artifact absent (no silent fallback).
- Probability output converted to {-1, 0, 1} via configurable thresholds stored in
  `Config.params_json`: `long_threshold` (default 0.6), `short_threshold` (default 0.4).
  Bars below `long_threshold` and above `short_threshold` → signal 0.
- Prediction uses only features with `available_at <= bar_timestamp` — enforced by
  `feature_builder` validation before inference; strategy raises if spec validation fails.
- `Strategy.logic_type = "ml_model"` and `model_class = "lightgbm"` accepted by
  `qw record` without schema errors.
- `vectorbt_adapter.run()` produces identical output structure to rule-based strategies.
- Unit tests: signal output in {-1, 0, 1}; missing artifact raises; threshold edge cases.
- `ruff check` and `mypy --strict` pass.
- `lightgbm` added to `pyproject.toml` dependencies.

## Repo Touchpoints
- `strategies/ml_signal_strategy.py` — new
- `tests/unit/test_ml_signal_strategy.py` — new
