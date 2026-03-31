"""
Experiment 3 — CL Stop Parameter Sweep (RSI Reversion)

Best params from 01_sweep locked: rsi=7, oversold=35, overbought=70, bb_period=20, bb_std=1.5
Sweeps sl_stop and tp_stop.

CL daily ATR ~2-3% vs MGC ~0.5-1%. The default SL (0.4%) is likely too
tight — getting stopped out on normal intraday noise and re-entering,
generating excess trades and fees. Testing wider stops calibrated to CL volatility.
"""
from data.store import get_store
from research.experiments.metrics import summary
from research.experiments.sweep import sweep
from strategies.rsi_reversion import RSIReversion

SYMBOL = "CL_continuous_1H"
FEES = 0.000005
LEVERAGE = 1.0
FREQ = "1H"
TIME_STOP = 8

# Best params from 01_sweep
BEST_PARAMS = {
    "rsi_period": [7],
    "oversold": [35],
    "overbought": [70],
    "bb_period": [20],
    "bb_std": [1.5],
}

store = get_store()
bars = store.read_bars("futures", SYMBOL)

bh_equity = bars["close"] / bars["close"].iloc[0] * 100_000
bh = summary(bh_equity)

print("=" * 10 + " METADATA " + "=" * 10)
print(f"SYMBOL:  CL_continuous_1H")
print(f"PARAMS:  rsi=7  oversold=35  overbought=70  bb_period=20  bb_std=1.5")
print(f"\n{'BH':>4}  sharpe={bh['sharpe']:+.3f}  dd={bh['max_drawdown']:+.2%}  ret={bh['return']:+.2%}")

stop_combos = [
    # (sl_stop, tp_stop)
    (0.004, 0.012),   # baseline from 01_sweep
    (0.006, 0.015),
    (0.006, 0.025),
    (0.010, 0.025),
    (0.010, 0.040),
    (0.015, 0.040),
    (0.015, 0.060),
    (0.020, 0.060),
    (0.020, 0.100),
    (0.025, 0.100),
]

print("\n" + "=" * 10 + " RESULTS " + "=" * 10)
print(f"  {'sl':>5}  {'tp':>5}  {'sharpe':>7}  {'vs BH':>7}  {'dd':>8}  {'ret':>8}  {'trades':>7}  beat_bh")

rows = []
for sl, tp in stop_combos:
    results = sweep(
        RSIReversion, bars,
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

# Best combo
if rows:
    best = max(rows, key=lambda r: r[2])
    print(f"\nBest: sl={best[0]:.1%}  tp={best[1]:.1%}  sharpe={best[2]:.3f}")
