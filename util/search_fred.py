"""Search FRED for HDD/CDD series IDs."""
from fredapi import Fred
from data.config import get_settings

fred = Fred(api_key=get_settings().fred_api_key)

# Try candidate IDs directly
candidates = ["HEATINGDD", "COOLINGDD", "HDDSUS", "CDDSUS", "HDD", "CDD",
              "NHDD", "NCDD", "DCOILWTICO"]
for sid in candidates:
    try:
        s = fred.get_series_info(sid)
        print(f"{sid}: {s.get('title','?')} | freq={s.get('frequency','?')} | {s.get('observation_start','?')} → {s.get('observation_end','?')}")
    except Exception as e:
        print(f"{sid}: not found ({e})")
