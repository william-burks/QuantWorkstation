# SIGNALS LIBRARY — ArcticDB Reference

The `signals` ArcticDB library is the shared store for anything derived from OHLCV bars:
strategy signals, regime labels, and other per-timestamp series that downstream research
consumes. Data bars themselves live in `crypto`, `futures`, etc. — not here.

---

## Library layout

ArcticDB libraries created by `Store`:

| Library | Purpose |
|---|---|
| `crypto` | Crypto OHLCV (symbol per ticker, e.g. `BTC/USD_1H`) |
| `futures` | Futures OHLCV — stitched, CONTFUT, and cash indices |
| `futures_meta` | FuturesContract metadata (symbol per root, e.g. `ES`) |
| `signals` | Derived series — strategies + regime classifiers |
| `calendar` | Roll calendars |

Defined in `data/store.py::_LIBRARIES`. All reads/writes must go through `Store` — never
touch `get_library()` directly (project rule).

---

## Key convention

Signal keys use a `<namespace>/<subject>` pattern. The namespace groups producers; the
subject is usually `<symbol>_<tf>`.

| Namespace | Key format | Producer | Notes |
|---|---|---|---|
| `<strategy>` | `<strategy>/<ticker>` | Strategy backtest output | Written via `Store.write_signals(strategy, symbol, df)`. Expects a `direction` column with values in {-1, 0, 1}. |
| `regime_atr` | `regime_atr/<symbol>_<tf>` | `research/regimes/atr_trend_classifier.py` (QWS-1403) | 4-label categorical series: `crisis`, `high_vol_trending`, `low_vol_ranging`, `transitional`. Currently seeded for `CL_1H`, `MES_1H`, `BTC/USD_1H`. |

---

## Read/write API

All access funnels through `data/store.py`.

```python
from data.store import Store

store = Store()

# Strategy signals
store.write_signals("bear_cl_sweep_1h", "CL_1H", df)      # df: DatetimeIndex + 'direction'
df = store.read_signals("bear_cl_sweep_1h", "CL_1H")

# Regime labels (classifier writes via overwrite_bars under the hood)
# Read back with the raw bars API using the fully-qualified key:
df = store.read_bars("signals", "regime_atr/CL_1H")
```

`write_signals()` handles strategy-namespaced keys. Other signal producers (regime
classifiers, etc.) use `Store.overwrite_bars("signals", key, df)` directly with a
pre-composed key.

---

## Regime signals — ATR classifier (QWS-1403)

Labels (see `research/regimes/atr_trend_classifier.py`):

| Label | Rule |
|---|---|
| `crisis` | ATR z-score > 2.0 AND ADX > 40 |
| `high_vol_trending` | ATR z-score > 0.5 AND ADX > 25 (not crisis) |
| `low_vol_ranging` | ATR z-score < 0 AND ADX < 20 |
| `transitional` | anything else |

Thresholds are frozen per QWS-1403 — not tuned by downstream strategies. `MAX_SINGLE_LABEL_FRACTION = 0.80` asserts no single label dominates the series, catching classifier drift.

Regenerate for a symbol:

```bash
python -m research.regimes.atr_trend_classifier --symbol CL
```

---

## Reference

- `data/store.py` — Store class, library list, read/write API
- `research/regimes/atr_trend_classifier.py` — current regime producer
- `qws_graph/epics/epic_14_research_pipeline_hardening/closed/story_QWS-1403_atr_regime_labels.md` — regime classifier acceptance criteria
