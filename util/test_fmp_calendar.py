"""Quick test: does FMP return historical economic calendar data with actuals?"""

import requests

from data.config import get_settings

settings = get_settings()
api_key = settings.fmp_api_key

resp = requests.get(
    "https://financialmodelingprep.com/stable/economic-calendar",
    params={"from": "2019-01-01", "to": "2019-03-31", "apikey": api_key},
    timeout=30,
)
print("Status:", resp.status_code)
data = resp.json()
print("Count:", len(data))
if data:
    print("First:", data[0])
    print("Last:", data[-1])
    with_actual = [r for r in data if r.get("actual") not in (None, "")]
    no_actual = [r for r in data if r.get("actual") in (None, "")]
    print(f"With actual: {len(with_actual)} / {len(data)}")
    print(f"Missing actual: {len(no_actual)} / {len(data)}")
    if with_actual:
        print("Sample with actual:", with_actual[0])
