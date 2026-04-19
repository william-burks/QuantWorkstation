"""
FRED ALFRED (Archival FRED) initial-release collector.

Fetches statistical macro releases as they were FIRST published — avoiding the
look-ahead bias introduced by FRED's default revised values.

Regular FRED: stores the most recent revision at each observation date.
  PCEPILFE[2021-03-01] = value BEA revised it to in 2023 → look-ahead bias.

ALFRED vintage (output_type=4): returns the initial-release value only.
  PCEPILFE[2021-03-01] = value released on 2021-03-26 → no look-ahead.

Critical implementation detail:
  Index = realtime_start (date the value was RELEASED to the public)
  Not:   date            (observation period the value COVERS)

  December CPI is released in January. A model trained at 2022-01-12 can see
  the December CPI only because realtime_start=2022-01-12. Indexing by
  observation date (2021-12-01) would let the model "see" December CPI a month
  early.

Series collected:
  CPIAUCSL  : CPI All Urban Consumers (monthly, ~Jan 15 release)
  CPILFESL  : Core CPI ex food & energy (monthly, same schedule)
  PCEPILFE  : Core PCE ex food & energy (monthly, ~last week of following month)
  PAYEMS    : Nonfarm Payrolls (monthly, first Friday after period end)
  UNRATE    : Unemployment Rate (monthly, same as PAYEMS)
  ICSA      : Initial Jobless Claims (weekly, Thursday release)
  RSAFS     : Retail Sales (monthly, ~mid month of following month)

ArcticDB key pattern: ``{SERIES_ID}_release_1D``
  e.g. ``CPIAUCSL_release_1D``, ``PAYEMS_release_1D``

Columns:
  ``value``    : float — initial-release value
  ``obs_date`` : datetime — observation period the value covers

Index: UTC DatetimeIndex — release date (realtime_start)

Incremental fetch: reads last stored release date, fetches only newer releases.

Auth: ``FRED_API_KEY`` env var (same as fred.py collector).

Run via: ``python -m data.collectors.fred_alfred``
"""

import logging
from datetime import timedelta

import pandas as pd
import requests

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

DEFAULT_START = "2019-01-01"

# Series IDs to collect as initial-release vintage data
ALFRED_SERIES: list[str] = [
    "CPIAUCSL",  # CPI All Urban Consumers
    "CPILFESL",  # Core CPI ex food & energy
    "PCEPILFE",  # Core PCE ex food & energy
    "PAYEMS",  # Nonfarm Payrolls
    "UNRATE",  # Unemployment Rate
    "ICSA",  # Initial Jobless Claims (weekly)
    "RSAFS",  # Retail Sales
]


def _arc_key(series_id: str) -> str:
    return f"{series_id}_release_1D"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _fetch_alfred(
    api_key: str,
    series_id: str,
    observation_start: str,
) -> pd.DataFrame:
    """Fetch initial-release vintage observations from ALFRED.

    Fetches all vintages from ``observation_start`` onwards, then filters to
    the earliest ``realtime_start`` per observation period — the initial release.

    Args:
        api_key: FRED API key.
        series_id: FRED series identifier (e.g. ``"CPIAUCSL"``).
        observation_start: ISO date string — earliest observation period to fetch
            (e.g. ``"2019-01-01"``). This is the period date, not the release date.

    Returns:
        DataFrame indexed by ``realtime_start`` (release date, UTC) with columns:
        ``value`` (float) and ``obs_date`` (datetime, the period the value covers).
        Empty DataFrame if no data returned.
    """
    params = {
        "series_id": series_id,
        "observation_start": observation_start,
        "realtime_start": observation_start,  # fetch all vintages from this date
        "realtime_end": "9999-12-31",
        "file_type": "json",
        "api_key": api_key,
    }
    resp = requests.get(FRED_API_BASE, params=params, timeout=30)
    resp.raise_for_status()

    payload = resp.json()
    observations = payload.get("observations", [])

    if not observations:
        return pd.DataFrame(columns=["value", "obs_date"])

    df = pd.DataFrame(observations)

    # Drop rows with missing/suppressed values
    df = df[df["value"] != "."].copy()
    if df.empty:
        return pd.DataFrame(columns=["value", "obs_date"])

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])

    df["obs_date"] = pd.to_datetime(df["date"], utc=True)
    df["release_date"] = pd.to_datetime(df["realtime_start"], utc=True)

    # Keep only the initial release per observation period:
    # sort by release_date ascending, then keep first per obs_date
    df = df.sort_values("release_date")
    df = df.drop_duplicates(subset=["obs_date"], keep="first")

    df = df.set_index("release_date")
    df.index.name = "release_date"

    return df[["value", "obs_date"]].sort_index()


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(series: list[str] | None = None) -> None:
    """Fetch ALFRED initial-release vintage data and write to ArcticDB.

    Writes to ``macro`` library under key ``{SERIES_ID}_release_1D``.
    Index is the release date (when data became public), not the observation
    period — use this index for all backtesting feature construction.

    Args:
        series: List of FRED series IDs. Defaults to ``ALFRED_SERIES``
            (CPI, core CPI, core PCE, NFP, unemployment, claims, retail sales).
    """
    settings = get_settings()
    api_key = settings.fred_api_key
    store = get_store()

    if series is None:
        series = list(ALFRED_SERIES)

    for series_id in series:
        arc_key = _arc_key(series_id)

        # Incremental: find last stored release date → map back to observation start
        observation_start = DEFAULT_START
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_release = existing.index.max()
                # Re-fetch from 60 days before last release to catch any
                # late-published initial releases (e.g. delayed government data)
                fetch_from = (last_release - timedelta(days=60)).date()
                observation_start = max(
                    pd.Timestamp(DEFAULT_START).date(),
                    fetch_from,
                ).strftime("%Y-%m-%d")
                log.info(
                    "%s: last release stored %s, fetching observations from %s",
                    series_id,
                    last_release.date(),
                    observation_start,
                )
        except Exception:
            log.info("%s: no existing data, fetching from %s", series_id, DEFAULT_START)

        df = _fetch_alfred(api_key, series_id, observation_start)

        if df.empty:
            log.info("%s: no data returned", series_id)
            continue

        # write_series upserts — existing rows win on duplicate release dates
        store.write_series("macro", arc_key, df)
        log.info(
            "Wrote %d rows to macro/%s  (%s → %s)",
            len(df),
            arc_key,
            df.index.min().date(),
            df.index.max().date(),
        )

    log.info("ALFRED collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
