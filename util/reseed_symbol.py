"""
Delete and reseed a single futures symbol/timeframe.

Usage:
    python3 util/reseed_symbol.py MGC 15min
"""
import sys

from data.collectors.ibkr_futures import _TIMEFRAMES, collect
from data.store import get_store

root = sys.argv[1] if len(sys.argv) > 1 else "MGC"
timeframe = sys.argv[2] if len(sys.argv) > 2 else "15min"
tf_cfg = _TIMEFRAMES.get(timeframe, {})
store_key = (
    f"{root}_contfut_{timeframe}" if tf_cfg.get("contfut") else f"{root}_{timeframe}"
)

store = get_store()
lib = store._libs["futures"]

if lib.has_symbol(store_key):
    lib.delete(store_key)
    print(f"Deleted {store_key}")
else:
    print(f"{store_key} not in store — seeding fresh")

collect(root, timeframe)
