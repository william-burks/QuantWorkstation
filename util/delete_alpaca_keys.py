"""Delete legacy Alpaca T-suffix crypto keys from ArcticDB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.store import get_store

KEYS = ["BTC/USD_1T", "BTC/USD_5T", "BTC/USD_15T", "ETH/USD_1T", "ETH/USD_5T", "ETH/USD_15T"]

store = get_store()
lib = store._ac.get_library("crypto")
for k in KEYS:
    lib.delete(k)
    print(f"Deleted crypto/{k}")
print("Done")
