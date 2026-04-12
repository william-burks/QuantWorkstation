# Epic 12 — ML Research Layer

## Objective

Extend research pipeline with ML-based regime classification and feature-engineered signal
generation. Rule-based and ML strategies compete on identical evaluation criteria.
Sharpe ≥ 2.0 | OOS ≥ 60 trades | walk-forward mandatory (N ≥ 3 folds) | no autonomous
training or promotion.

## Entry Criteria

- QWS-0502 CLOSED (Regime nodes exist — HMM labels written via same path)
- QWS-0803 CLOSED (Decay monitor — ML Champions decay faster; monitor must be live before
  any ML Champion can be promoted)
- `walk_forward.py` stable (used as reference harness for ml_walk_forward.py)

## Exit Criteria

At least one ML Champion in the graph with verified OOS Sharpe ≥ 2.0 across ≥ 3
walk-forward folds and ≥ 2 regimes.

## Schema Changes (Strategy node only)

Three new optional properties — no new node types:

| Property | Values | Rule-based default |
|---|---|---|
| `logic_type` | adds `"ml_model"`, `"ml_regime"` to existing values | existing value unchanged |
| `model_class` | `str \| null` — e.g. `"lightgbm"`, `"hmm"` | `null` |
| `feature_spec_path` | `str \| null` — path to feature YAML | `null` |

`Config.params_json` stores ML hyperparams alongside rule-based params. Run, Champion,
FormerChampion, correlation gate all work unchanged.

## Implementation Phases

| Phase | Stories | Theme |
|---|---|---|
| 1 — Prerequisite | QWS-1201 | Purge gap parameter |
| 2 — Regime | QWS-1202 | HMM regime classifier |
| 3 — Features | QWS-1203 | Feature engineering layer |
| 4 — Harness | QWS-1204 | ML walk-forward harness |
| 5 — Signal | QWS-1205 | LightGBM signal model |
| 6 — Agents | QWS-1206, QWS-1207 | Results interpreter + Hypothesis miner |

## Overfitting Guards (non-negotiable — enforced in QWS-1204)

- `n_parameters / n_trades < 0.05`
- IS/OOS Sharpe ratio > 2.0 → flag OVERFIT
- OOS trades < 60 → flag INSUFFICIENT_SAMPLE before promotion
- Walk-forward: N ≥ 3 folds mandatory
- Regime diversity: Sharpe ≥ 2.0 in > 1 regime (via `regime_performance` query)

## Story Execution Order

```
QWS-1201 (purge gap)
    └── QWS-1202 (HMM) ∥ QWS-1203 (feature builder)
                              └── QWS-1204 (ml walk-forward harness)
                                      └── QWS-1205 (LightGBM signal model)
                                      └── QWS-1206 (results interpreter)
                                              └── QWS-1207 (hypothesis miner)
```

## Stories

| Story | ID | Status | Effort | Blocked On |
|---|---|---|---|---|
| Walk-forward Purge Gap | QWS-1201 | READY | S | — |
| HMM Regime Classifier | QWS-1202 | READY | M | QWS-1201 |
| Feature Engineering Layer | QWS-1203 | PLANNED | M | QWS-1201 |
| ML Walk-forward Harness | QWS-1204 | PLANNED | M | QWS-1203 |
| LightGBM Signal Model | QWS-1205 | PLANNED | M | QWS-1204 |
| Results Interpreter Agent | QWS-1206 | PLANNED | S | QWS-1204 |
| Hypothesis Miner Agent | QWS-1207 | PLANNED | S | QWS-1206 |

## Approach Constraints

- HMM first, LightGBM second
- No LSTM, no RL, no AutoML
- All ML strategies use identical lifecycle: Hypothesis → Strategy → Trial → Run → Champion
- "AI navigates; researcher decides" — ML same as rule-based
