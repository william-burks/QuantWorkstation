"""
Experiment 1 — Dual-TF Trend Baseline (Futures CL 1H)

4H EMA bias filter + 1H EMA crossover entry.
Sweep ltf_fast/ltf_slow (1H) and htf_fast/htf_slow (4H).

SL/TP wider than reversion: trend trades need room to run.
Time stop is long (7 days) — exits via signal in practice.
"""
from data.store import get_store
from research.experiments.evaluator import evaluate, report
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.dual_tf_trend import DualTFTrend

SYMBOL = "CL_continuous_1H"
FEES = 0.000005
LEVERAGE = 1.0
SL_STOP = 0.010
TP_STOP = 0.040
TIME_STOP = 168   # 7 days on 1H bars — exits via signal in practice

store = get_store()
bars = store.read_bars("futures", SYMBOL)

bh_equity = bars["close"] / bars["close"].iloc[0] * 100_000
bh = summary(bh_equity)

bars_5min = store.read_bars("futures", "CL_continuous_5min")
data_span = (
    f"{bars_5min.index.min().strftime('%Y-%m-%d %H:%M')} → "
    f"{bars_5min.index.max().strftime('%Y-%m-%d %H:%M')} "
    f"({len(bars_5min):,} 5min bars)"
)

metadata = {
    "strategy":  "dual_tf_trend",
    "symbol":    SYMBOL,
    "freq":      "1H",
    "leverage":  LEVERAGE,
    "fees":      FEES,
    "sl_stop":   SL_STOP,
    "tp_stop":   TP_STOP,
    "time_stop": TIME_STOP,
    "data_span": data_span,
}

results = sweep(
    DualTFTrend, bars,
    param_grid={
        "ltf_fast": [8, 12, 21],
        "ltf_slow": [21, 34, 50],
        "htf_fast": [8, 12],
        "htf_slow": [21, 34],
    },
    freq="1H",
    leverage=LEVERAGE,
    fees=FEES,
    sl_stop=SL_STOP,
    tp_stop=TP_STOP,
    time_stop=TIME_STOP,
)

results = evaluate(results, bh)
report(results, bh, metadata)
