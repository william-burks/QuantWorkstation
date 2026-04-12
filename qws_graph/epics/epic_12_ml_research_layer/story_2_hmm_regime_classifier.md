# Story 2 — HMM Regime Classifier

## ID
QWS-1202

## Status
READY

## Blocked On
QWS-1201 (purge gap — HMM walk-forward uses `purge_bars` to prevent leakage from rolling
volatility features)

## Summary
New file `research/models/hmm_regime.py` — Hidden Markov Model trained on return series +
realized volatility from ArcticDB. Outputs per-bar regime posterior probabilities and MAP
state labels. Regime labels written to graph via existing `qw record --regime` path.
Extends QWS-1003 (planned rule-based classifier) — HMM labels can replace or supplement
rule-based thresholds. Walk-forward: expanding window train, label test window with frozen
trained model.

## Problem
Existing regime tagging (QWS-0502) requires manually defined thresholds (e.g. vol percentile
buckets). These thresholds are static and require periodic recalibration as market structure
shifts. An HMM learns regime boundaries from the data itself, providing a more adaptive
classifier and a grounded alternative to hand-coded rules. This is Phase 1 of ML integration:
no lookahead features, no signal generation — regime classification only.

## Goal

```python
# Train and label
from research.models.hmm_regime import HMMRegimeClassifier

clf = HMMRegimeClassifier(n_states=3)
clf.fit(returns, realized_vol)          # expanding window
labels = clf.predict(returns, realized_vol)  # MAP state per bar
posteriors = clf.predict_proba(returns, realized_vol)  # (n_bars, n_states)

# Record to graph via existing CLI
qw record --regime BullLow <run_id>
```

## Schema Extension

### Strategy node — new optional properties
| Property | Value | Rule-based default |
|---|---|---|
| `logic_type` | `"ml_regime"` (new enum value) | existing value unchanged |
| `model_class` | `"hmm"` | `null` |
| `feature_spec_path` | `null` (HMM uses return + vol only — no separate spec needed) | `null` |

All other nodes (Run, Champion, FormerChampion, Regime, IN_REGIME) unchanged.
Regime labels written with same `qw record --regime` command as rule-based classifiers.

## Design

### HMMRegimeClassifier
```python
class HMMRegimeClassifier:
    def __init__(self, n_states: int = 3, covariance_type: str = "full",
                 n_iter: int = 100, random_state: int = 42): ...

    def fit(self, returns: pd.Series, realized_vol: pd.Series) -> "HMMRegimeClassifier":
        """Fits on full provided window. Returns self."""

    def predict(self, returns: pd.Series, realized_vol: pd.Series) -> pd.Series:
        """Returns MAP state labels (int) aligned to input index."""

    def predict_proba(self, returns: pd.Series, realized_vol: pd.Series) -> pd.DataFrame:
        """Returns posterior probabilities, columns = [state_0, state_1, ...]."""

    def save(self, path: str) -> None: ...
    def load(self, path: str) -> "HMMRegimeClassifier": ...
```

### Inputs (from ArcticDB — no new data collection needed)
- `returns`: 1-bar log returns from existing bar data
- `realized_vol`: rolling std of returns (window configurable, default 20 bars)

### Walk-forward protocol
- Expanding window: train on bars 1..T, label bars T+1..T+K
- `purge_bars` applied at fold boundary (from QWS-1201) — default 0 for HMM (no rolling
  features in the classifier itself, but purge_bars accepted for consistency)
- Model serialized per fold to `research/models/<experiment_id>/fold_N_hmm.pkl`

### State labeling convention
States are unlabeled by the HMM (arbitrary integers). Labeling is manual: Will inspects
regime statistics (`mean_return`, `mean_vol` per state) and assigns semantic names before
calling `qw record --regime`. No autonomous label assignment.

### n_states selection
Configurable. Walk-forward run with `n_states` in {2, 3, 4, 5} — best AIC/BIC selects
final model. Selection is logged; Will confirms before any graph write.

## In Scope
- `research/models/__init__.py` — new (package init)
- `research/models/hmm_regime.py` — HMMRegimeClassifier implementation
- `research/experiments/` — example notebook / trial script demonstrating walk-forward
  HMM training (numbered trial, e.g. `01_hmm_regime_btc.py`)
- `qws_graph/docs/data_dictionary.yaml` — document `logic_type = "ml_regime"`,
  `model_class`, `feature_spec_path` on Strategy node
- `docs/PROVENANCE_ENGINE.md` — add ml_regime to Strategy.logic_type enum docs
- Unit tests: fit/predict roundtrip; predict output length matches input; save/load
  preserves predictions; n_states out of range raises ValueError
- Integration test: end-to-end walk-forward with mock return series

## Out of Scope
- Autonomous regime labeling (Will assigns semantic names)
- Signal generation from regime labels (QWS-1205)
- Feature spec YAML (HMM uses return + vol directly — no spec needed)
- `qw record --regime` CLI changes (existing path sufficient)

## Repo Touchpoints
- `research/models/__init__.py` — new
- `research/models/hmm_regime.py` — new
- `research/trials/01_hmm_regime_btc.py` — new (or next available trial number)
- `qws_graph/docs/data_dictionary.yaml`
- `docs/PROVENANCE_ENGINE.md`
- `tests/unit/test_hmm_regime.py` — new
- `tests/integration/test_hmm_walk_forward.py` — new

## Acceptance Criteria
- [ ] `HMMRegimeClassifier.fit(returns, realized_vol)` completes without error on 2-year
  BTC/USD_1H data from ArcticDB.
- [ ] `predict()` output length equals input length; all values are valid state integers
  in range [0, n_states-1].
- [ ] `predict_proba()` output shape is (n_bars, n_states); each row sums to 1.0 ± 1e-6.
- [ ] Save/load roundtrip: loaded model produces identical predictions to in-memory model
  on held-out test data.
- [ ] Walk-forward trial script runs end-to-end with N ≥ 3 folds; per-fold model artifacts
  written to `research/models/<experiment_id>/fold_N_hmm.pkl`.
- [ ] `n_states` outside [2, 5] raises `ValueError` with descriptive message.
- [ ] `Strategy.logic_type = "ml_regime"` and `model_class = "hmm"` accepted by
  `qw record` without schema errors.
- [ ] `data_dictionary.yaml` documents new Strategy properties.
- [ ] `PROVENANCE_ENGINE.md` updated with ml_regime logic_type.
- [ ] `ruff check` and `mypy --strict` pass with no new violations.
- [ ] `hmmlearn` added to `pyproject.toml` dependencies.

## Definition of Done
- [ ] `hmm_regime.py` implemented and tested.
- [ ] Walk-forward trial script operational.
- [ ] Schema docs updated (data_dictionary.yaml + PROVENANCE_ENGINE.md).
- [ ] Unit and integration tests pass.
- [ ] Story marked CLOSED.
