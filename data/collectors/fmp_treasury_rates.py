"""
FMP Treasury Rates collector.

Fetches the full US Treasury yield curve (1M → 30Y) from the FMP
``/stable/treasury-rates`` endpoint and writes it to the ``macro`` ArcticDB
library.

Complements the FRED collector which only tracks DGS2, DGS10, T10Y2Y.
This adds: 1M, 2M, 3M, 6M, 1Y, 3Y, 5Y, 7Y, 20Y maturities.

ArcticDB key: ``TREASURY_RATES_1D``
Columns: month1, month2, month3, month6, year1, year2, year3, year5,
         year7, year10, year20, year30
Index: UTC DatetimeIndex

API limit: max 90-day date range per request.
Incremental: reads last stored date and fetches forward in 90-day chunks.

Run via: ``python -m data.collectors.fmp_treasury_rates``
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/stable/treasury-rates"
ARC_KEY = "TREASURY_RATES_1D"
ARC_LIB = "macro"
CHUNK_DAYS = 89  # stay under 90-day API limit
RATE_COLUMNS = [
    "month1", "month2", "month3", "month6",
    "year1", "year2", "year3", "year5",
    "year7", "year10", "year20", "year30",
]
# Starter plan: 5 years of history
HISTORY_YEARS = 5


def _fetch_chunk(api_key: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch one 90-day chunk of treasury rates."""
    params = {"from": from_date, "to": to_date, "apikey": api_key}
    resp = requests.get(FMP_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if not payload:
        return pd.DataFrame(columns=RATE_COLUMNS)

    df = pd.DataFrame(payload)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()

    for col in RATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = float("nan")

    return df[RATE_COLUMNS]


def collect() -> None:
    """Fetch full yield curve and write to ArcticDB ``macro`` library."""
    settings = get_settings()
    api_key = settings.fmp_api_key
    store = get_store()

    today = datetime.now(UTC).date()

    # Determine start date
    start_date = today - timedelta(days=HISTORY_YEARS * 365)
    try:
        existing = store.read_series(ARC_LIB, ARC_KEY)
        if not existing.empty:
            last = existing.index.max().date()
            start_date = last + timedelta(days=1)
            log.info("TREASURY_RATES: last stored %s, fetching from %s", last, start_date)
    except Exception:
        log.info("TREASURY_RATES: no existing data, fetching %d years of history", HISTORY_YEARS)

    if start_date > today:
        log.info("TREASURY_RATES: already up to date")
        return

    # Fetch in 90-day chunks
    chunks: list[pd.DataFrame] = []
    chunk_start = start_date
    while chunk_start <= today:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), today)
        log.info("TREASURY_RATES: fetching %s to %s", chunk_start, chunk_end)
        df = _fetch_chunk(api_key, chunk_start.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d"))
        if not df.empty:
            chunks.append(df)
        chunk_start = chunk_end + timedelta(days=1)

    if not chunks:
        log.info("TREASURY_RATES: no new data")
        return

    combined = pd.concat(chunks).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    store.write_series(ARC_LIB, ARC_KEY, combined)
    log.info("Wrote %d rows to %s/%s", len(combined), ARC_LIB, ARC_KEY)
    log.info("Treasury rates collection complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
