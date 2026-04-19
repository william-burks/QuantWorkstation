"""
Financial Modeling Prep (FMP) economic calendar collector.

Fetches upcoming and historical macro events (FOMC, NFP, CPI, etc.) from the
FMP ``/v3/economic_calendar`` endpoint and writes them into the ``calendar``
ArcticDB library via ``store.write_series()``.

ArcticDB key: ``ECON_CALENDAR``
Index: ``release_datetime`` — UTC-aware DatetimeIndex
Columns:
  - ``event_name``  : str  — FMP ``event`` field
  - ``previous``    : float — prior release value; NaN if unavailable
  - ``consensus``   : float — analyst estimate; NaN if unavailable
  - ``actual``      : float — confirmed value; NaN before release
  - ``impact``      : str  — ``high`` / ``medium`` / ``low``
  - ``is_blackout`` : bool — True where impact == 'high'

Rolling window: -7 days to +30 days from today; idempotent upsert.
API: free tier, 250 calls/day.

Run via: ``python -m data.collectors.economic_calendar``
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FMP_BASE_URL = "https://financialmodelingprep.com/stable/economic-calendar"
ARC_SYMBOL = "ECON_CALENDAR"
ARC_LIB = "calendar"
WINDOW_PAST_DAYS = 7
WINDOW_FUTURE_DAYS = 30


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _fetch_calendar(api_key: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch economic calendar events from FMP.

    Args:
        api_key: FMP API key.
        from_date: ISO date string (``YYYY-MM-DD``) — start of window.
        to_date: ISO date string (``YYYY-MM-DD``) — end of window.

    Returns:
        DataFrame with UTC DatetimeIndex (``release_datetime``) and columns:
        ``event_name``, ``previous``, ``consensus``, ``actual``, ``impact``,
        ``is_blackout``.

    Raises:
        requests.HTTPError: if the API returns a non-2xx status.
    """
    params: dict[str, str] = {
        "from": from_date,
        "to": to_date,
        "apikey": api_key,
    }
    response = requests.get(FMP_BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()

    if not payload:
        return _empty_df()

    df = pd.DataFrame(payload)

    # Rename FMP fields → internal column names
    df = df.rename(
        columns={
            "event": "event_name",
            "estimate": "consensus",
        }
    )

    # Parse release_datetime index
    df["release_datetime"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("release_datetime").sort_index()

    # Coerce numeric columns — actual is NaN before release, not 0
    df["previous"] = pd.to_numeric(df.get("previous", pd.Series(dtype=float)), errors="coerce")
    df["consensus"] = pd.to_numeric(df.get("consensus", pd.Series(dtype=float)), errors="coerce")
    df["actual"] = pd.to_numeric(df.get("actual", pd.Series(dtype=float)), errors="coerce")

    # impact: keep as-is string; default to 'low' if missing
    df["impact"] = df.get("impact", pd.Series(dtype=str)).fillna("low").astype(str)

    # Derived blackout flag
    df["is_blackout"] = df["impact"].str.lower() == "high"

    return df[["event_name", "previous", "consensus", "actual", "impact", "is_blackout"]]


def _empty_df() -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    idx = pd.DatetimeIndex([], name="release_datetime", tz="UTC")
    return pd.DataFrame(
        columns=["event_name", "previous", "consensus", "actual", "impact", "is_blackout"],
        index=idx,
    )


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect() -> None:
    """Fetch economic calendar and write to ArcticDB ``calendar`` library.

    Uses a rolling window of -7 days to +30 days relative to today.
    Idempotent: ``write_series`` deduplicates by index before writing.
    """
    settings = get_settings()
    api_key = settings.fmp_api_key
    store = get_store()

    today = datetime.now(tz=UTC).date()
    from_date = (today - timedelta(days=WINDOW_PAST_DAYS)).strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=WINDOW_FUTURE_DAYS)).strftime("%Y-%m-%d")

    log.info("EconCalendar: fetching %s to %s", from_date, to_date)
    df = _fetch_calendar(api_key, from_date, to_date)

    if df.empty:
        log.info("EconCalendar: no events in window")
        return

    store.write_series(ARC_LIB, ARC_SYMBOL, df)
    log.info("Wrote %d events to %s/%s", len(df), ARC_LIB, ARC_SYMBOL)
    log.info("EconCalendar collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
