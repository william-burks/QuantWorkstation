"""
Wipe all futures stitched data and reseed a single symbol across all
stitched timeframes (5min, 15min, 1H, 4H). CONTFUT timeframes (1D, 1W)
are unaffected.

Usage:
    python3 util/reseed_all_stitched.py MGC
"""

import sys

from data.collectors.ibkr_futures import _TIMEFRAMES, collect
from data.store import get_store

STITCHED = [tf for tf, cfg in _TIMEFRAMES.items() if not cfg["contfut"]]

store = get_store()
lib = store._libs["futures"]
root = sys.argv[1] if len(sys.argv) > 1 else "MGC"

# Wipe all symbols in the futures library
all_symbols = lib.list_symbols()
print(f"\n=== Wiping futures library ({len(all_symbols)} symbols) ===")
for sym in all_symbols:
    lib.delete(sym)
    print(f"  Deleted {sym}")

# Reseed target symbol across all stitched timeframes
print(f"\n=== Reseeding {root} — {len(STITCHED)} timeframes: {STITCHED} ===\n")
for i, tf in enumerate(STITCHED, 1):
    print(f"[{i}/{len(STITCHED)}] {root} {tf}")
    try:
        collect(root, tf)
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n=== Done ===")
