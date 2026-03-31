"""
Delete and reseed a single futures symbol/timeframe.

Usage:
    python3 util/reseed_symbol.py MGC 15min
"""
import sys
from data.store import get_store
from data.collectors.ibkr_futures import collect

root = sys.argv[1] if len(sys.argv) > 1 else "MGC"
timeframe = sys.argv[2] if len(sys.argv) > 2 else "15min"
store_key = f"{root}_continuous_{timeframe}"

store = get_store()
lib = store._libs["futures"]

if lib.has_symbol(store_key):
    lib.delete(store_key)
    print(f"Deleted {store_key}")
else:
    print(f"{store_key} not in store — seeding fresh")

collect(root, timeframe)
