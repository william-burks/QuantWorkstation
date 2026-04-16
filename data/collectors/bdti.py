"""
Baltic Dirty Tanker Index (BDTI) collector.

Scrapes the current BDTI value from StockQ and appends it to the ``macro``
ArcticDB library via ``store.write_series()``.

Historical seed: run ``python util/seed_bdti_history.py`` once to load the
Investing.com CSV export (Apr 2016 onward).

ArcticDB key: ``BDTI_1D``
Column: ``value`` (BDTI composite index level, float)
Index: UTC DatetimeIndex (date-level, time set to 00:00 UTC)

Incremental fetch: reads last stored date; skips write if today is already
present.

Run via: ``python -m data.collectors.bdti``
"""

import logging
from datetime import UTC, datetime

import pandas as pd
import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from data.store import get_store

log = logging.getLogger(__name__)

STOCKQ_URL = "https://en.stockq.org/index/BDTI.php"
ARC_KEY = "BDTI_1D"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _fetch_bdti() -> float:
    """Scrape current BDTI value from StockQ.

    Returns:
        BDTI index level as float.

    Raises:
        ValueError: if the value cannot be parsed from the page.
        requests.HTTPError: if the request fails.
    """
    resp = requests.get(STOCKQ_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # StockQ layout: large number in a <td class="tdtable1"> or similar;
    # the index value appears as the first numeric cell after the header row.
    # Fallback: search all td text for a plausible BDTI value (500–5000).
    for td in soup.find_all("td"):
        text = td.get_text(strip=True).replace(",", "")
        try:
            val = float(text)
            if 200 <= val <= 10000:
                return val
        except ValueError:
            continue

    raise ValueError("Could not parse BDTI value from StockQ page")


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect() -> None:
    """Fetch current BDTI and append to ArcticDB ``macro`` library.

    Skips the write if today's date is already stored.
    """
    store = get_store()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        existing = store.read_series("macro", ARC_KEY)
        if not existing.empty and existing.index.max() >= pd.Timestamp(today):
            log.info("BDTI: already up to date (%s)", existing.index.max().date())
            return
    except Exception:
        log.info("BDTI: no existing data")

    value = _fetch_bdti()
    log.info("BDTI: fetched %.2f for %s", value, today.date())

    df = pd.DataFrame({"value": [value]}, index=pd.DatetimeIndex([today]))
    store.write_series("macro", ARC_KEY, df)
    log.info("Wrote 1 row to macro/%s", ARC_KEY)
    log.info("BDTI collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
