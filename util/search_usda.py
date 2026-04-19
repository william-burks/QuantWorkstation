"""Find valid unit_desc values for CORN PROGRESS from NASS API."""

import requests

from data.config import get_settings

key = get_settings().usda_api_key
r = requests.get(
    "https://quickstats.nass.usda.gov/api/api_GET/",
    params={
        "key": key,
        "commodity_desc": "SOYBEANS",
        "statisticcat_desc": "PROGRESS",
        "freq_desc": "WEEKLY",
        "year__GE": "2024",
        "format": "JSON",
    },
    timeout=30,
)
r.raise_for_status()
data = r.json().get("data", [])
units = sorted(set(row["unit_desc"] for row in data))
print("Valid unit_desc values for CORN PROGRESS:")
for u in units:
    print(f"  {u!r}")
