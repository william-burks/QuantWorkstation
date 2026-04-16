"""Clear specified symbols from ArcticDB macro lib."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.store import get_store

KEYS = [
    "BHI_US_TOTAL_RIGS", "BHI_US_OIL_RIGS", "BHI_US_GAS_RIGS", "BHI_CANADA_RIGS",
]

store = get_store()
lib = store._get_lib("macro")
existing = lib.list_symbols()
for key in KEYS:
    if key in existing:
        lib.delete(key)
        print(f"Deleted macro/{key}")
    else:
        print(f"macro/{key} not found — skipping")
