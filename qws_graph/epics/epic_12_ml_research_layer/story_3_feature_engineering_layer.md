# Story 3 — Feature Engineering Layer

## ID
QWS-1203

## Status
PLANNED

## Blocked On
QWS-1201 (purge_bars — feature builder must accept purge_bars to validate lookahead-safe
feature availability at bar T)

## Summary
New `research/features/` directory for YAML feature specs. New
`research/experiments/feature_builder.py` builds feature DataFrames from spec + ArcticDB
data. Every feature spec declares `lookahead_risk`; mechanical guard validates
`feature.available_at <= bar_timestamp` for every row before any training run. Starter
library covers multi-horizon returns, rolling vol, ATR, volume ratio, RSI, calendar
features, and conditional external data (COT, VIX when available).

## Key ACs
- Feature spec YAML validated for lookahead before training. Any feature failing the check
  raises an error — no silent skip.
- `feature_builder.py` returns aligned DataFrame with no future-peeking rows.
- Starter library: multi-horizon returns (1, 4, 12, 24 bar), rolling vol (10, 20, 60),
  ATR (14), volume ratio vs. 20-bar mean, RSI (14), hour-of-day, day-of-week, month,
  pre/post-settlement flag.
- COT percentile rank and VIX level implemented as optional features with `available_at`
  set to data delivery lag; skipped gracefully when data absent.
- Each feature spec includes: `name`, `series`, `transform`, `lookahead_risk`,
  `prior_usage` (list of run_ids that used this feature — populated manually).
- `ruff check` and `mypy --strict` pass.

## Dependencies
QWS-1204 (ML walk-forward harness) consumes feature_builder output.

## Repo Touchpoints
- `research/features/` — new directory
- `research/features/schema.yaml` — feature spec schema definition
- `research/features/starter_library.yaml` — starter features
- `research/experiments/feature_builder.py` — new
- `tests/unit/test_feature_builder.py` — new
