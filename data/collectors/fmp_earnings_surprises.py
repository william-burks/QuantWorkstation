"""
FMP Earnings Surprises collector.

Fetches EPS actual vs estimate for key S&P 500 / Nasdaq 100 constituents
from the FMP ``/stable/earnings`` endpoint and writes them to the ``macro``
ArcticDB library.

Used as an event-driven alpha signal: post-earnings drift on equity index
futures (MES/MNQ/ES/NQ) when large-cap constituents beat or miss.

ArcticDB key: ``EARNINGS_SURPRISES``
Columns: symbol, actual_eps, estimated_eps, surprise, surprise_pct, revenue,
         estimated_revenue
Index: UTC DatetimeIndex (earnings date)

Incremental: skips symbols with up-to-date data; re-fetches all on first run.

Run via: ``python -m data.collectors.fmp_earnings_surprises``
"""

import logging
import time
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/stable/earnings"
ARC_KEY = "EARNINGS_SURPRISES"
ARC_LIB = "macro"
REQUEST_DELAY = 0.25  # seconds between requests (300 calls/min limit)

# Top S&P 500 / Nasdaq 100 constituents — largest index weight movers
# These drive MES/ES/MNQ/NQ index-level moves on earnings
SYMBOLS = [
    # Mega-cap tech (heavy NQ/MNQ weight)
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "TSLA",
    "AVGO",
    "ORCL",
    # Financials (heavy SPX weight)
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "BLK",
    "SCHW",
    "C",
    "AXP",
    "COF",
    # Healthcare
    "UNH",
    "JNJ",
    "LLY",
    "ABBV",
    "MRK",
    "PFE",
    "TMO",
    "ABT",
    "MDT",
    "CVS",
    # Energy (CL/NG correlation)
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "MPC",
    "PSX",
    "VLO",
    "OXY",
    "HES",
    # Industrials / macro-sensitive
    "CAT",
    "DE",
    "BA",
    "GE",
    "HON",
    "MMM",
    "UPS",
    "FDX",
    "LMT",
    "RTX",
    # Consumer
    "AMZN",
    "HD",
    "MCD",
    "SBUX",
    "NKE",
    "TGT",
    "WMT",
    "COST",
    "LOW",
    "TJX",
    # Semis (NQ driver)
    "AMD",
    "INTC",
    "QCOM",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "TXN",
    "MRVL",
    "ON",
    # Gold / commodity proxies (GC/MGC correlation)
    "NEM",
    "GOLD",
    "AEM",
    "WPM",
    "FNV",
]
# Deduplicate preserving order
_seen: set[str] = set()
SYMBOLS = [s for s in SYMBOLS if s not in _seen and not _seen.add(s)]  # type: ignore[func-returns-value]


def _fetch_symbol(api_key: str, symbol: str) -> pd.DataFrame:
    """Fetch earnings history for one symbol."""
    params = {"symbol": symbol, "apikey": api_key}
    resp = requests.get(FMP_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if not payload:
        return pd.DataFrame()

    df = pd.DataFrame(payload)

    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    if date_col is None:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    actual_col = next(
        (c for c in df.columns if "actual" in c.lower() and "eps" in c.lower()), None
    ) or next((c for c in df.columns if "actual" in c.lower()), None)
    est_col = next(
        (c for c in df.columns if "estimat" in c.lower() and "eps" in c.lower()), None
    ) or next((c for c in df.columns if "estimat" in c.lower()), None)
    rev_col = next(
        (
            c
            for c in df.columns
            if "revenue" in c.lower() and "actual" not in c.lower() and "estimat" not in c.lower()
        ),
        None,
    )
    est_rev_col = next(
        (c for c in df.columns if "estimat" in c.lower() and "revenue" in c.lower()), None
    )

    result = pd.DataFrame(index=df.index)
    result["symbol"] = symbol
    result["actual_eps"] = (
        pd.to_numeric(df[actual_col], errors="coerce") if actual_col else float("nan")
    )
    result["estimated_eps"] = (
        pd.to_numeric(df[est_col], errors="coerce") if est_col else float("nan")
    )
    result["surprise"] = result["actual_eps"] - result["estimated_eps"]
    result["surprise_pct"] = (result["surprise"] / result["estimated_eps"].abs()).replace(
        [float("inf"), float("-inf")], float("nan")
    )
    result["revenue"] = pd.to_numeric(df[rev_col], errors="coerce") if rev_col else float("nan")
    result["estimated_revenue"] = (
        pd.to_numeric(df[est_rev_col], errors="coerce") if est_rev_col else float("nan")
    )

    return result


def collect() -> None:
    """Fetch earnings surprises for key constituents and write to ArcticDB."""
    settings = get_settings()
    api_key = settings.fmp_api_key
    store = get_store()

    # Load existing to determine what needs updating
    existing_max_date: dict[str, pd.Timestamp] = {}
    try:
        existing = store.read_series(ARC_LIB, ARC_KEY)
        if not existing.empty and "symbol" in existing.columns:
            for sym, grp in existing.groupby("symbol"):
                existing_max_date[str(sym)] = grp.index.max()
    except Exception:
        pass

    stale_cutoff = datetime.now(UTC) - timedelta(days=90)
    chunks: list[pd.DataFrame] = []

    for symbol in SYMBOLS:
        last = existing_max_date.get(symbol)
        if last is not None and last.to_pydatetime().replace(tzinfo=UTC) > stale_cutoff:
            log.info("EARNINGS: %s up to date (last %s)", symbol, last.date())
            continue

        log.info("EARNINGS: fetching %s", symbol)
        try:
            df = _fetch_symbol(api_key, symbol)
            if not df.empty:
                chunks.append(df)
                log.info("  → %d records", len(df))
        except Exception as e:
            log.warning("  → failed: %s", e)

        time.sleep(REQUEST_DELAY)

    if not chunks:
        log.info("EARNINGS_SURPRISES: all symbols up to date")
        return

    new_data = pd.concat(chunks).sort_index()
    new_data.index += pd.to_timedelta(new_data.groupby(level=0).cumcount(), unit="ns")

    # Merge: keep existing rows for symbols not re-fetched
    try:
        existing = store.read_series(ARC_LIB, ARC_KEY)
        if not existing.empty and "symbol" in existing.columns:
            refreshed = set(new_data["symbol"].unique())
            existing = existing[~existing["symbol"].isin(refreshed)]
            combined = pd.concat([existing, new_data]).sort_index()
        else:
            combined = new_data
    except Exception:
        combined = new_data

    store.write_series(ARC_LIB, ARC_KEY, combined)
    log.info("Wrote %d total rows to %s/%s", len(combined), ARC_LIB, ARC_KEY)
    log.info("Earnings surprises collection complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
