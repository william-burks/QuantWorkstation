"""
Experiment 2 — Stop Parameter Sweep (Dual-TF Trend)

Best params from 01_baseline locked. Sweeps sl_stop and tp_stop.
Tests both TP-gated and signal-only (high TP ~= no TP) exit modes.

For trend following, TP cuts winners short. The hypothesis is that
wider TP (or effectively no TP) improves risk-adjusted returns by
letting winning trades run to signal exit rather than price target.
"""
from data.store import get_store
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.dual_tf_trend import DualTFTrend

SYMBOL = "CL_continuous_1H"
FEES = 0.000005
LEVERAGE = 1.0
FREQ = "1H"
TIME_STOP = 168

# Best params from 01_baseline — update if symbol or baseline results change
BEST_PARAMS = {
    "ltf_fast": [21],
    "ltf_slow": [50],
    "htf_fast": [12],
    "htf_slow": [21],
}

store = get_store()
bars = store.read_bars("futures", SYMBOL)

bh_equity = bars["close"] / bars["close"].iloc[0] * 100_000
bh = summary(bh_equity)

print("=" * 10 + " METADATA " + "=" * 10)
print(f"SYMBOL:  {SYMBOL}")
print(f"PARAMS:  ltf=21/50  htf=12/21")
print(f"\n{'BH':>4}  sharpe={bh['sharpe']:+.3f}  dd={bh['max_drawdown']:+.2%}  ret={bh['return']:+.2%}")

stop_combos = [
    # (sl_stop, tp_stop) — progress from tight to wide, then signal-only
    (0.008, 0.024),   # baseline from 01_baseline
    (0.010, 0.040),
    (0.010, 0.080),
    (0.015, 0.040),
    (0.015, 0.080),
    (0.015, 0.150),
    (0.020, 0.080),
    (0.020, 0.150),
    (0.025, 0.150),
    (0.025, 0.300),   # ~= signal-only for most trades
]

print("\n" + "=" * 10 + " RESULTS " + "=" * 10)
print(f"  {'sl':>5}  {'tp':>5}  {'sharpe':>7}  {'vs BH':>7}  {'dd':>8}  {'ret':>8}  {'trades':>7}  beat_bh")

rows = []
for sl, tp in stop_combos:
    results = sweep(
        DualTFTrend, bars,
        param_grid=BEST_PARAMS,
        freq=FREQ,
        leverage=LEVERAGE,
        fees=FEES,
        sl_stop=sl,
        tp_stop=tp,
        time_stop=TIME_STOP,
    )
    if results.empty:
        continue
    row = results.iloc[0]
    beat = row["sharpe"] > bh["sharpe"]
    rows.append((sl, tp, row["sharpe"], row["max_drawdown"], row["return"], row["n_trades"], beat))
    print(
        f"  {sl:.1%}  {tp:.1%}  {row['sharpe']:>7.3f}  "
        f"{row['sharpe'] - bh['sharpe']:>+7.3f}  "
        f"{row['max_drawdown']:>8.2%}  {row['return']:>8.2%}  "
        f"{int(row['n_trades']):>7}  {'YES' if beat else 'no'}"
    )

if rows:
    best = max(rows, key=lambda r: r[2])
    print(f"\nBest: sl={best[0]:.1%}  tp={best[1]:.1%}  sharpe={best[2]:.3f}")
