"""
Baltic Dirty Tanker Index (BDTI) collector.

Fetches the daily BDTI value via the Nasdaq Data Link (Quandl) REST API and
writes it into the ``macro`` ArcticDB library via ``store.write_series()``.

Dataset: ``BWAVE/BDTI`` — Baltic Exchange daily dirty tanker route composite
         (available on Nasdaq Data Link free tier as of implementation).

If the BWAVE/BDTI dataset is unavailable on the free tier, obtain the
dataset code from https://data.nasdaq.com/search?query=BDTI and update the
``NDQL_DATASET`` constant below.  A free-tier API key can be registered at
https://data.nasdaq.com.

ArcticDB key: ``BDTI_1D``
Column: ``value`` (BDTI composite index level, float)
Index: UTC DatetimeIndex

Incremental fetch: reads last stored date, passes ``start_date`` query param
so only new rows are fetched on subsequent runs.

Run via: ``python -m data.collectors.bdti``
"""

import logging
from datetime import timedelta

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NDQL_BASE_URL = "https://data.nasdaq.com/api/v3/datasets"
NDQL_DATASET = "BWAVE/BDTI"
ARC_KEY = "BDTI_1D"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _fetch_bdti(api_key: str, start_date: str | None) -> pd.DataFrame:
    """Fetch BDTI data from Nasdaq Data Link REST API.

    Args:
        api_key: Nasdaq Data Link API key.
        start_date: ISO date string (``YYYY-MM-DD``) for incremental fetch,
            or None for full history.

    Returns:
        DataFrame with UTC DatetimeIndex and single column ``value``.

    Raises:
        requests.HTTPError: if the API returns a non-2xx status.
    """
    url = f"{NDQL_BASE_URL}/{NDQL_DATASET}.json"
    params: dict[str, str] = {
        "api_key": api_key,
        "order": "asc",
    }
    if start_date is not None:
        params["start_date"] = start_date

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    dataset = payload.get("dataset", {})
    data = dataset.get("data", [])

    if not data:
        return pd.DataFrame(columns=["value"])

    df = pd.DataFrame(data, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect() -> None:
    """Fetch BDTI data and write to ArcticDB ``macro`` library.

    Reads last stored date from ArcticDB to perform an incremental fetch.
    Creates the ``macro`` library if it does not exist.
    """
    settings = get_settings()
    api_key = settings.nasdaq_data_link_api_key
    store = get_store()

    start_date: str | None = None
    try:
        existing = store.read_series("macro", ARC_KEY)
        if not existing.empty:
            last_date = existing.index.max()
            next_date = last_date + timedelta(days=1)
            start_date = next_date.strftime("%Y-%m-%d")
            log.info(
                "BDTI: last stored %s, fetching from %s",
                last_date.date(),
                start_date,
            )
    except Exception:
        log.info("BDTI: no existing data, fetching full history")

    df = _fetch_bdti(api_key, start_date)

    if df.empty:
        log.info("BDTI: no new data to write")
        return

    store.write_series("macro", ARC_KEY, df)
    log.info("Wrote %d rows to macro/%s", len(df), ARC_KEY)
    log.info("BDTI collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
