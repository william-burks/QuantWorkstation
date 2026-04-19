"""
FMP Insider Trading collector.

Fetches insider trades from the FMP ``/stable/insider-trading/search``
endpoint, one symbol at a time, for the equity universe defined in
``fmp_earnings_surprises.SYMBOLS`` (~75 names).

Why per-symbol: the ``/latest`` all-market endpoint caps at ~5,000 rows
(50 pages × 100), covering only ~1 week of activity. The per-symbol
``/search`` endpoint supports date filtering, enabling multi-year history.

Signal use: aggregate insider buying clusters across equity universe as a
smart-money directional signal, particularly for large-cap constituents
that drive MES/MNQ index moves.

ArcticDB key: ``INSIDER_TRADES``
Columns: symbol, reporting_name, transaction_type, acquisition_or_disposition,
         securities_transacted, price, securities_owned
Index: UTC DatetimeIndex (filing date, nanosecond-offset to ensure uniqueness)

Run via: ``python -m data.collectors.fmp_insider_trades``
"""

import logging
import time
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.collectors.fmp_earnings_surprises import SYMBOLS
from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/stable/insider-trading/search"
ARC_KEY = "INSIDER_TRADES"
ARC_LIB = "macro"
PAGE_LIMIT = 100
LOOKBACK_DAYS = 365  # initial seed depth
MAX_PAGES = 20  # per symbol (2,000 rows ≈ years of history per name)
REQUEST_DELAY = 0.25  # seconds between requests (300 calls/min limit)


def _fetch_symbol_pages(api_key: str, symbol: str, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Fetch all insider-trade pages for one symbol, stopping at cutoff."""
    frames: list[pd.DataFrame] = []

    for page in range(MAX_PAGES):
        params = {
            "symbol": symbol,
            "page": page,
            "limit": PAGE_LIMIT,
            "apikey": api_key,
        }
        resp = requests.get(FMP_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        if not payload:
            break

        df = pd.DataFrame(payload)

        date_col = next(
            (c for c in df.columns if "filing" in c.lower() and "date" in c.lower()), None
        )
        if date_col is None:
            date_col = next((c for c in df.columns if "date" in c.lower()), None)
        if date_col is None:
            break

        df["_date"] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
        df = df.dropna(subset=["_date"])
        if df.empty:
            break

        frames.append(df)

        if df["_date"].min() < cutoff:
            break

        time.sleep(REQUEST_DELAY)

    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["_date"] >= cutoff]

    col_map = {
        "symbol": next((c for c in raw.columns if c.lower() == "symbol"), None),
        "reporting_name": next(
            (c for c in raw.columns if "reporting" in c.lower() and "name" in c.lower()), None
        ),
        "transaction_type": next(
            (
                c
                for c in raw.columns
                if "transactiontype" in c.lower() or "transaction_type" in c.lower()
            ),
            None,
        ),
        "acquisition_or_disposition": next(
            (c for c in raw.columns if "acquisition" in c.lower() or "acquis" in c.lower()), None
        ),
        "securities_transacted": next(
            (
                c
                for c in raw.columns
                if "transacted" in c.lower() or "securitiestransacted" in c.lower()
            ),
            None,
        ),
        "price": next((c for c in raw.columns if c.lower() == "price"), None),
        "securities_owned": next((c for c in raw.columns if "owned" in c.lower()), None),
    }

    result = pd.DataFrame(index=range(len(raw)))
    for target, source in col_map.items():
        result[target] = raw[source].values if source and source in raw.columns else None

    result["_date"] = raw["_date"].values
    for col in ["securities_transacted", "price", "securities_owned"]:
        result[col] = pd.to_numeric(result[col], errors="coerce")

    return result


def collect() -> None:
    """Fetch insider trades for all equity universe symbols and write to ArcticDB."""
    settings = get_settings()
    api_key = settings.fmp_api_key
    store = get_store()

    # Load existing data once; use it to determine per-symbol cutoffs
    try:
        existing = store.read_series(ARC_LIB, ARC_KEY)
    except Exception:
        existing = pd.DataFrame()

    default_cutoff = pd.Timestamp(datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).tz_convert(
        "UTC"
    )

    all_frames: list[pd.DataFrame] = []

    for symbol in SYMBOLS:
        # Per-symbol cutoff: last stored filing date minus 7-day overlap
        if not existing.empty and "symbol" in existing.columns:
            sym_rows = existing[existing["symbol"] == symbol]
            if not sym_rows.empty:
                cutoff = sym_rows.index.max() - timedelta(days=7)
                cutoff = pd.Timestamp(cutoff).tz_convert("UTC")
                log.info(
                    "%s: last stored %s, fetching from %s",
                    symbol,
                    sym_rows.index.max().date(),
                    cutoff.date(),
                )
            else:
                cutoff = default_cutoff
                log.info("%s: no existing data, fetching %d days", symbol, LOOKBACK_DAYS)
        else:
            cutoff = default_cutoff
            log.info("%s: no existing data, fetching %d days", symbol, LOOKBACK_DAYS)

        try:
            df = _fetch_symbol_pages(api_key, symbol, cutoff)
            if not df.empty:
                all_frames.append(df)
                log.info("%s: fetched %d rows", symbol, len(df))
        except Exception as exc:
            log.warning("%s: fetch failed — %s", symbol, exc)

        time.sleep(REQUEST_DELAY)

    if not all_frames:
        log.info("INSIDER_TRADES: no new data")
        return

    new_data = pd.concat(all_frames, ignore_index=True)

    # Build DatetimeIndex with nanosecond offsets so duplicate filing dates stay distinct
    new_data = new_data.sort_values("_date").reset_index(drop=True)
    new_data["_date"] = new_data["_date"] + pd.to_timedelta(new_data.index, unit="ns")
    new_data = new_data.set_index("_date")
    new_data.index.name = "filing_date"

    # Drop old overlap window rows for affected symbols, then concatenate
    if not existing.empty and "symbol" in existing.columns:
        updated_symbols = set(new_data["symbol"].dropna().unique())
        keep_existing = existing[~existing["symbol"].isin(updated_symbols)]

        # For each updated symbol, trim rows older than its new data
        for symbol in updated_symbols:
            sym_new = new_data[new_data["symbol"] == symbol]
            if sym_new.empty:
                continue
            sym_cutoff = sym_new.index.min() - timedelta(days=7)
            sym_old = existing[(existing["symbol"] == symbol) & (existing.index < sym_cutoff)]
            keep_existing = pd.concat([keep_existing, sym_old])

        combined = pd.concat([keep_existing, new_data]).sort_index()
    else:
        combined = new_data

    store.write_series(ARC_LIB, ARC_KEY, combined)
    log.info("Wrote %d total rows to %s/%s", len(combined), ARC_LIB, ARC_KEY)
    log.info("Insider trades collection complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
