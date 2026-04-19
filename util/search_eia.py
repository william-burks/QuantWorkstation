"""Verify EIA HDD/CDD series range and frequency."""

import requests

from data.config import get_settings

KEY = get_settings().eia_api_key
BASE = "https://api.eia.gov/v2"


def get(route: str, params: dict | None = None) -> dict:
    p = {"api_key": KEY}
    if params:
        p.update(params)
    r = requests.get(f"{BASE}{route}", params=p, timeout=15)
    r.raise_for_status()
    return r.json().get("response", {})


for msn in ["ZWHDPUS", "ZWCDPUS"]:
    oldest = get(
        "/total-energy/data/",
        {
            "facets[msn][]": msn,
            "length": "1",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        },
    )
    newest = get(
        "/total-energy/data/",
        {
            "facets[msn][]": msn,
            "length": "1",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
        },
    )
    total = oldest.get("total", 0)
    first = oldest.get("data", [{}])[0]
    last = newest.get("data", [{}])[0]
    print(
        f"{msn}: {total} rows | {first.get('period')} → {last.get('period')} | unit={first.get('unit')} | value={first.get('value')}"
    )
