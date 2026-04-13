"""
EIA (U.S. Energy Information Administration) crude oil inventory collector.

Fetches weekly petroleum stock series via the EIA v2 open data REST API and
writes them into the ``macro`` ArcticDB library via ``store.write_series()``.

Series collected:
  - WCRSTUS1  : US crude oil stocks (total) — headline number
  - WCSSTUS1  : Cushing, OK crude oil stocks
  - WGTSTUS1  : US total gasoline stocks
  - WDISTUS1  : US distillate fuel oil stocks

ArcticDB key pattern: ``EIA_{SERIES_ID}``  (e.g. ``EIA_WCRSTUS1``)
Columns: ``value`` (raw inventory level, thousands barrels), ``surprise``
    (week-over-week change: ``value - value.shift(1)``)
Index: UTC DatetimeIndex

Incremental fetch: reads last stored date, requests only newer observations
so subsequent runs append rather than re-pull full history.

Run via: ``python -m data.collectors.eia``
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

EIA_ENDPOINT = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

DEFAULT_SERIES: list[str] = [
    "WCRSTUS1",
    "WCSSTUS1",
    "WGTSTUS1",
    "WDISTUS1",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arc_key(series_id: str) -> str:
    """Return ArcticDB key for an EIA series ID."""
    return f"EIA_{series_id}"


def _fetch_series(
    api_key: str,
    series_id: str,
    start_date: str | None,
) -> pd.DataFrame:
    """Fetch a single EIA petroleum stock series.

    Args:
        api_key: EIA open data API key.
        series_id: EIA series identifier (e.g. ``"WCRSTUS1"``).
        start_date: ISO date string (``YYYY-MM-DD``) for incremental fetch,
            or None for full history.

    Returns:
        DataFrame with UTC DatetimeIndex and columns ``value`` and ``surprise``.
        Rows with null values are dropped. ``surprise`` is the week-over-week
        change (``value.diff(1)``); the first row has NaN surprise and is kept
        to preserve continuity but is expected to be NaN.
    """
    params: dict[str, str | list[str]] = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[]": "value",
        "facets[series][]": f"PET.{series_id}.W",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": "5000",
    }
    if start_date is not None:
        params["start"] = start_date

    response = requests.get(EIA_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    rows = payload.get("response", {}).get("data", [])

    if not rows:
        return pd.DataFrame(columns=["value", "surprise"])

    df = pd.DataFrame(rows)
    df = df[["period", "value"]].copy()
    df["period"] = pd.to_datetime(df["period"], utc=True)
    df = df.rename(columns={"period": "date"})
    df = df.set_index("date")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.sort_index()
    df["surprise"] = df["value"].diff(1)
    return df


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(series: list[str] | None = None) -> None:
    """Fetch EIA petroleum stock series and write to ArcticDB ``macro`` library.

    Args:
        series: List of EIA series IDs to collect. Defaults to
            ``DEFAULT_SERIES`` (4 weekly petroleum stock series).
    """
    settings = get_settings()
    if series is None:
        series = list(settings.eia_series)

    api_key = settings.eia_api_key
    store = get_store()

    for series_id in series:
        arc_key = _arc_key(series_id)

        # Incremental: find last stored date
        start_date: str | None = None
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_date = existing.index.max()
                next_date = last_date + timedelta(days=1)
                start_date = next_date.strftime("%Y-%m-%d")
                log.info(
                    "Series %s: last stored %s, fetching from %s",
                    series_id,
                    last_date.date(),
                    start_date,
                )
        except Exception:
            log.info("Series %s: no existing data, fetching full history", series_id)

        df = _fetch_series(api_key, series_id, start_date)

        if df.empty:
            log.info("Series %s: no new data to write", series_id)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("EIA collection complete for %s", series)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
