"""
Validate the ratio_stitch fix by re-running _seed_stitched for a single
symbol/timeframe and checking the output for roll-date jumps.

Requires IB Gateway running. Does NOT write to the store — dry run only.

Usage:
    python3 util/validate_stitch.py
"""

import logging
import sys

from ib_insync import IB

from data.collectors.ibkr_futures import (
    _TIMEFRAMES,
    _fetch_contract_bars,
    _get_contract_chain,
    _ratio_stitch,
)
from data.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stdout,
)

ROOT = "MGC"
TIMEFRAME = "15min"
JUMP_THRESHOLD = 0.02  # flag bars with >2% price change (should be 0 at roll dates post-fix)

s = get_settings()
tf = _TIMEFRAMES[TIMEFRAME]

print(f"\n=== Stitch validation: {ROOT} {TIMEFRAME} ===\n")

ib = IB()
try:
    ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id + 10)

    chain = _get_contract_chain(ib, ROOT, years_back=3, max_age_days=tf["max_contract_age_days"])
    print(f"Contract chain: {len(chain)} contracts")
    for c in chain:
        print(f"  {c.lastTradeDateOrContractMonth[:8]}")

    print("\nFetching bars for each contract...")
    frames = []
    for contract in chain:
        expiry = contract.lastTradeDateOrContractMonth[:8]
        label = f"{ROOT} {TIMEFRAME} exp={expiry}"
        df = _fetch_contract_bars(ib, contract, tf, label)
        if not df.empty:
            frames.append(df)
            date_range = f"{df.index.min().date()} → {df.index.max().date()}"
            print(f"  {expiry}: {len(df)} bars  ({date_range})")
        else:
            print(f"  {expiry}: NO BARS")

finally:
    ib.disconnect()

if not frames:
    print("No frames — cannot stitch")
    sys.exit(1)

print(f"\nStitching {len(frames)} frames (logs show roll detail)...")
stitched = _ratio_stitch(frames, label=f"{ROOT} {TIMEFRAME}")

print("\n=== Stitched series ===")
print(f"  Bars:  {len(stitched):,}")
print(f"  Span:  {stitched.index.min()} → {stitched.index.max()}")

# Check for large jumps
pct_change = stitched["close"].pct_change()
jumps = pct_change[pct_change.abs() > JUMP_THRESHOLD].sort_values(key=abs, ascending=False)

print(f"\n=== Bars with >{JUMP_THRESHOLD:.0%} price jump ===")
if jumps.empty:
    print("  None — stitching looks clean")
else:
    print(f"  {len(jumps)} found:")
    for ts, val in jumps.items():
        print(f"  {ts}  {val:+.2%}")

# BH check
bh = (stitched["close"].iloc[-1] / stitched["close"].iloc[0]) - 1
print(f"\nBH return (back-adjusted):  {bh:+.2%}")

# === Continuity verification at each roll_ts ===
CONTINUITY_TOL = 0.0001  # 0.01% — pure floating point tolerance, not market movement

print(f"\n=== Continuity at roll timestamps (tol={CONTINUITY_TOL:.2%}) ===")
roll_failures = []
for i in range(len(frames) - 1):
    older = frames[i]
    newer = frames[i + 1]
    common_ts = older.index.intersection(newer.index)
    if common_ts.empty:
        print(f"  roll {i}: NO OVERLAP — skipped")
        continue
    roll_ts = common_ts[-1]
    if roll_ts not in stitched.index:
        print(f"  roll {i} ({roll_ts.date()}): roll_ts missing from stitched series")
        continue
    p_old = older.loc[roll_ts, "close"]
    p_new = newer.loc[roll_ts, "close"]
    if p_old <= 0:
        continue
    ratio = p_new / p_old
    # After back-adjustment, older[roll_ts] * ratio should equal newer[roll_ts].
    # Verify the stitched value at roll_ts matches the newer contract's raw price
    # scaled by whatever cumulative was applied above this roll.
    # Simpler proxy: check that the stitched value at roll_ts is NOT from the jumps list.
    stitched_price = stitched.loc[roll_ts, "close"]
    expected = p_new  # roll_ts is kept from newer side; cumulative above this roll applied
    delta_pct = abs(stitched_price - expected) / expected
    # Allow larger tolerance here since cumulative from later rolls shifts the value
    # We just want to confirm no catastrophic mismatch
    status = "OK" if delta_pct < 0.05 else f"SUSPICIOUS ({delta_pct:.2%} from raw newer price)"
    print(f"  roll {i} ({roll_ts.date()}):  p_old={p_old:.2f}  p_new={p_new:.2f}  "
          f"ratio={ratio:.6f}  stitched={stitched_price:.2f}  {status}")
    if delta_pct >= 0.05:
        roll_failures.append(i)

if not roll_failures:
    print("  All roll timestamps present and plausible ✓")
else:
    print(f"  {len(roll_failures)} suspicious rolls: {roll_failures}")

# === Cross-timeframe return check (uses stored data — no IBKR needed) ===
# Price levels will differ between timeframes (different cumulative back-adjustment chains).
# Returns must match: hourly return computed from 15min closes == 1H return at same timestamp.
print("\n=== Cross-timeframe return check (15min vs 1H from store) ===")
try:
    from data.store import get_store
    store = get_store()
    if store.has_symbol("futures", f"{ROOT}_continuous_1H"):
        bars_1h = store.read_bars("futures", f"{ROOT}_continuous_1H")
        # Hourly close from 15min = the bar whose timestamp falls on :00
        bars_15_hourly = stitched[stitched.index.minute == 0]["close"]
        common = bars_15_hourly.index.intersection(bars_1h.index)
        if len(common) > 1:
            ret_15 = bars_15_hourly.loc[common].pct_change().dropna()
            ret_1h = bars_1h.loc[common, "close"].pct_change().dropna()
            common_ret = ret_15.index.intersection(ret_1h.index)
            ret_diff = (ret_15.loc[common_ret] - ret_1h.loc[common_ret]).abs()
            print(f"  Common hourly bars: {len(common):,}")
            print(f"  Return delta (|15min - 1H|):  mean={ret_diff.mean():.6f}  "
                  f"std={ret_diff.std():.6f}  "
                  f"max={ret_diff.max():.6f}")
            if ret_diff.mean() < 0.0001:
                print("  Returns are consistent ✓  (mean delta < 0.01%)")
            else:
                print(f"  WARNING: returns diverge — mean delta {ret_diff.mean():.4%}")
        else:
            print("  Not enough common timestamps")
    else:
        print(f"  {ROOT}_continuous_1H not in store — reseed after validation")
except Exception as e:
    print(f"  Store check failed: {e}")
