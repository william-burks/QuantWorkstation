"""
FRED (Federal Reserve Economic Data) macro collector.

Fetches key daily macro series (yield curve, credit spreads, VIX) via the
``fredapi`` Python package and writes them into the ``macro`` ArcticDB library
via ``store.write_series()``.

Series collected:
  - DGS2          : 2-year Treasury yield
  - DGS10         : 10-year Treasury yield
  - T10Y2Y        : 10Y-2Y yield spread (pre-computed by FRED)
  - VIXCLS        : CBOE VIX close
  - BAMLH0A0HYM2  : ICE BofA High Yield OAS

ArcticDB key pattern: ``{SERIES_ID}_1D``  (e.g. ``DGS10_1D``)
Column: ``value`` (single-column; no OHLCV)
Index: UTC DatetimeIndex

Incremental fetch: reads last stored date, passes ``observation_start`` to FRED
so only new data is fetched on subsequent runs.

Run via: ``python -m data.collectors.fred``
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
from typing import Any

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default series
# ---------------------------------------------------------------------------

DEFAULT_SERIES: list[str] = [
    "DGS2",
    "DGS10",
    "T10Y2Y",
    "VIXCLS",
    "BAMLH0A0HYM2",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arc_key(series_id: str) -> str:
    """Return ArcticDB key for a FRED series ID."""
    return f"{series_id}_1D"


def _fetch_series(
    fred_client: Any,
    series_id: str,
    observation_start: str | None,
) -> pd.DataFrame:
    """Fetch a single FRED series and return a single-column DataFrame.

    Args:
        fred_client: An initialised ``fredapi.Fred`` instance.
        series_id: FRED series identifier (e.g. ``"DGS10"``).
        observation_start: ISO date string for incremental fetch, or None for
            full history.

    Returns:
        DataFrame with DatetimeIndex (UTC) and a single column named ``value``.
        Rows with NaN values are dropped (FRED uses NaN for missing/weekend rows).
    """
    kwargs: dict[str, str] = {}
    if observation_start is not None:
        kwargs["observation_start"] = observation_start

    raw: pd.Series = fred_client.get_series(series_id, **kwargs)

    if not isinstance(raw.index, pd.DatetimeIndex):
        raw.index = pd.to_datetime(raw.index)

    raw.index = raw.index.tz_localize("UTC")
    df = raw.to_frame(name="value")
    df = df.dropna(subset=["value"])
    df = df.sort_index()
    return df


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(series: list[str] | None = None) -> None:
    """Fetch FRED series and write to ArcticDB ``macro`` library.

    Args:
        series: List of FRED series IDs to collect. Defaults to
            ``DEFAULT_SERIES`` (5 key macro indicators).
    """
    try:
        import fredapi
    except ImportError as exc:
        raise ImportError(
            "fredapi package not installed. Add 'fredapi' to project dependencies."
        ) from exc

    if series is None:
        settings = get_settings()
        series = list(settings.fred_series)

    store = get_store()
    api_key = get_settings().fred_api_key
    fred = fredapi.Fred(api_key=api_key)

    for series_id in series:
        arc_key = _arc_key(series_id)

        # Incremental: find last stored date
        observation_start: str | None = None
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_date = existing.index.max()
                # Start from the day after last stored date
                next_date = last_date + timedelta(days=1)
                observation_start = next_date.strftime("%Y-%m-%d")
                log.info(
                    "Series %s: last stored %s, fetching from %s",
                    series_id,
                    last_date.date(),
                    observation_start,
                )
        except Exception:
            # Library or symbol does not exist yet — full fetch
            log.info("Series %s: no existing data, fetching full history", series_id)

        df = _fetch_series(fred, series_id, observation_start)

        if df.empty:
            log.info("Series %s: no new data to write", series_id)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("FRED collection complete for %s", series)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
