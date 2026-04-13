"""
NOAA Climate Data Online (CDO) degree day collector.

Fetches weekly Heating Degree Days (HDD) and Cooling Degree Days (CDD) for
US national and regional series via the NOAA CDO v2 REST API and writes them
into the ``macro`` ArcticDB library via ``store.write_series()``.

Series collected (ArcticDB key → description):
  - NOAA_HDD_NATIONAL  : US national Heating Degree Days  (locationid=CLIM:US, datatypeid=HDD)
  - NOAA_CDD_NATIONAL  : US national Cooling Degree Days  (locationid=CLIM:US, datatypeid=CDD)
  - NOAA_HDD_NORTHEAST : Northeast region HDD             (locationid=CLIM:R1, datatypeid=HDD)
  - NOAA_HDD_MIDWEST   : Midwest region HDD               (locationid=CLIM:R4, datatypeid=HDD)

ArcticDB key pattern: ``NOAA_{TYPE}_{REGION}``
Columns: ``value`` (degree days, float)
Index: UTC DatetimeIndex (weekly)

Incremental fetch: reads last stored date, requests only newer observations.

Auth: ``NOAA_API_KEY`` env var (free from https://www.ncdc.noaa.gov/cdo-web/token).
Do NOT add to .env — stored as export in ~/.zshrc per security rules.

Run via: ``python -m data.collectors.noaa``
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

NOAA_CDO_ENDPOINT = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

# Each entry: (arc_key, datatypeid, locationid)
NOAA_SERIES: list[tuple[str, str, str]] = [
    ("NOAA_HDD_NATIONAL", "HDD", "CLIM:US"),
    ("NOAA_CDD_NATIONAL", "CDD", "CLIM:US"),
    ("NOAA_HDD_NORTHEAST", "HDD", "CLIM:R1"),
    ("NOAA_HDD_MIDWEST", "HDD", "CLIM:R4"),
]

# Default arc_keys for config / CLI use
DEFAULT_SERIES: list[str] = [arc_key for arc_key, _, _ in NOAA_SERIES]

# Lookup from arc_key → (datatypeid, locationid)
_SERIES_MAP: dict[str, tuple[str, str]] = {
    arc_key: (dtype, loc) for arc_key, dtype, loc in NOAA_SERIES
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_series(
    api_key: str,
    arc_key: str,
    start_date: str | None,
) -> pd.DataFrame:
    """Fetch a single NOAA CDO degree-day series.

    Args:
        api_key: NOAA CDO API token (from NOAA_API_KEY env var).
        arc_key: ArcticDB key identifying which series to fetch
            (must be a key in ``_SERIES_MAP``).
        start_date: ISO date string (``YYYY-MM-DD``) for incremental fetch,
            or None for full history (NOAA CDO limit: 1000 rows per call,
            but weekly data rarely exceeds that).

    Returns:
        DataFrame with UTC DatetimeIndex and column ``value`` (float).
        Empty DataFrame (with ``value`` column) if no results.
    """
    datatypeid, locationid = _SERIES_MAP[arc_key]

    params: dict[str, str] = {
        "datasetid": "NORMAL_ANN",
        "datatypeid": datatypeid,
        "locationid": locationid,
        "units": "standard",
        "limit": "1000",
        "sortfield": "date",
        "sortorder": "asc",
    }

    # NOAA CDO requires startdate/enddate; default to full span if not incremental
    if start_date is not None:
        params["startdate"] = start_date
        # enddate = today
        params["enddate"] = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    else:
        # Fetch last 10 years of weekly data by default
        end = pd.Timestamp.now(tz="UTC")
        start = end - pd.DateOffset(years=10)
        params["startdate"] = start.strftime("%Y-%m-%d")
        params["enddate"] = end.strftime("%Y-%m-%d")

    headers = {"token": api_key}

    response = requests.get(NOAA_CDO_ENDPOINT, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    payload = response.json()
    rows = payload.get("results", [])

    if not rows:
        return pd.DataFrame(columns=["value"])

    df = pd.DataFrame(rows)
    # CDO returns date as ISO string; value is numeric
    df = df[["date", "value"]].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.sort_index()
    return df


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(series: list[str] | None = None) -> None:
    """Fetch NOAA degree-day series and write to ArcticDB ``macro`` library.

    Args:
        series: List of ArcticDB keys to collect. Defaults to ``DEFAULT_SERIES``
            (4 weekly degree-day series).
    """
    settings = get_settings()
    if series is None:
        series = list(settings.noaa_series)

    api_key = settings.noaa_api_key
    store = get_store()

    for arc_key in series:
        if arc_key not in _SERIES_MAP:
            log.warning("Unknown NOAA series key %s — skipping", arc_key)
            continue

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
                    arc_key,
                    last_date.date(),
                    start_date,
                )
        except Exception:
            log.info("Series %s: no existing data, fetching full history", arc_key)

        df = _fetch_series(api_key, arc_key, start_date)

        if df.empty:
            log.info("Series %s: no new data to write", arc_key)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("NOAA collection complete for %s", series)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
