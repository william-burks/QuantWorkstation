"""
Google Trends retail sentiment collector.

Fetches weekly interest scores (0–100) for configurable search terms via the
``pytrends`` unofficial library and writes them into the ``macro`` ArcticDB
library via ``store.write_series()``.

Terms collected (default):
  - "buy gold"             → GTRENDS_BUY_GOLD
  - "gold inflation hedge" → GTRENDS_GOLD_INFLATION_HEDGE
  - "recession"            → GTRENDS_RECESSION
  - "inflation"            → GTRENDS_INFLATION

ArcticDB key pattern: ``GTRENDS_{SLUG}``
Column: ``interest`` (int 0–100, Google normalized score)
Index:  UTC DatetimeIndex aligned to Monday of reported week

Rate limiting: 60s sleep between requests. On HTTP 429/500 (ResponseError),
sleep 120s and retry once; if second attempt also fails, log warning and skip.

Run via: ``python -m data.collectors.google_trends``
"""

import logging
import re
import time

import pandas as pd

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: pytrends (unofficial Google Trends library)
# ---------------------------------------------------------------------------

try:
    from pytrends.exceptions import ResponseError
    from pytrends.request import TrendReq

    _PYTRENDS_AVAILABLE = True
except ImportError:
    TrendReq = None
    ResponseError = Exception
    _PYTRENDS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TERMS: list[str] = [
    "buy gold",
    "gold inflation hedge",
    "recession",
    "inflation",
]

_SLEEP_BETWEEN_TERMS: float = 60.0
_RETRY_SLEEP: float = 120.0
_TIMEFRAME: str = "today 5-y"

# Max date range for weekly granularity from Google Trends API
_MAX_WEEKLY_YEARS: int = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arc_key(term: str) -> str:
    """Return ArcticDB key for a Google Trends search term.

    Uppercases the term, replaces spaces with underscores, strips
    non-alphanumeric/underscore characters.

    Examples:
        "buy gold"            → "GTRENDS_BUY_GOLD"
        "gold inflation hedge"→ "GTRENDS_GOLD_INFLATION_HEDGE"
    """
    slug = term.upper().replace(" ", "_")
    slug = re.sub(r"[^A-Z0-9_]", "", slug)
    return f"GTRENDS_{slug}"


def _fetch_term_range(term: str, timeframe: str) -> pd.DataFrame:
    """Fetch Google Trends interest for a single term with an explicit timeframe string.

    timeframe must be a pytrends-compatible string, e.g.:
      "today 5-y"               — rolling 5-year window (weekly)
      "2019-01-06 2024-01-05"   — explicit date range ≤5yr (weekly)

    Returns DataFrame with UTC DatetimeIndex and ``interest`` column (int 0–100).
    Returns empty DataFrame on failure.
    """
    if not _PYTRENDS_AVAILABLE or TrendReq is None:
        log.error("pytrends not installed — cannot collect Google Trends data")
        return pd.DataFrame(columns=["interest"])

    def _build_and_fetch() -> pd.DataFrame:
        pt = TrendReq(hl="en-US", tz=0)
        pt.build_payload([term], timeframe=timeframe)
        raw: pd.DataFrame = pt.interest_over_time()
        if raw.empty:
            return pd.DataFrame(columns=["interest"])
        df = raw[[term]].rename(columns={term: "interest"}).copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df["interest"] = df["interest"].astype(int)
        return df

    try:
        return _build_and_fetch()
    except ResponseError as exc:
        log.warning(
            "Google Trends ResponseError for %r (timeframe=%s): %s — retrying in %ss",
            term,
            timeframe,
            exc,
            _RETRY_SLEEP,
        )
        time.sleep(_RETRY_SLEEP)
        try:
            return _build_and_fetch()
        except ResponseError as exc2:
            log.warning("Google Trends second failure for %r: %s — skipping", term, exc2)
            return pd.DataFrame(columns=["interest"])
    except Exception as exc:
        log.error(
            "Unexpected error fetching Google Trends for %r (timeframe=%s): %s — skipping",
            term,
            timeframe,
            exc,
        )
        return pd.DataFrame(columns=["interest"])


def _fetch_term(term: str) -> pd.DataFrame:
    """Fetch weekly Google Trends interest for a single search term.

    Uses ``pytrends.TrendReq`` to pull the last 5-year weekly time series.
    Returns a DataFrame with UTC DatetimeIndex and an ``interest`` column
    (int 0–100).  Returns an empty DataFrame on failure rather than raising.

    Retry policy: on ``ResponseError`` (HTTP 429 or 500), sleep
    ``_RETRY_SLEEP`` seconds and retry once. Second failure → empty DataFrame.
    """
    if not _PYTRENDS_AVAILABLE or TrendReq is None:
        log.error("pytrends not installed — cannot collect Google Trends data")
        return pd.DataFrame(columns=["interest"])

    def _build_and_fetch() -> pd.DataFrame:
        pt = TrendReq(hl="en-US", tz=0)
        pt.build_payload([term], timeframe=_TIMEFRAME)
        raw: pd.DataFrame = pt.interest_over_time()
        if raw.empty:
            return pd.DataFrame(columns=["interest"])
        df = raw[[term]].rename(columns={term: "interest"}).copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df["interest"] = df["interest"].astype(int)
        return df

    try:
        return _build_and_fetch()
    except ResponseError as exc:
        log.warning(
            "Google Trends ResponseError for %r: %s — retrying in %ss",
            term,
            exc,
            _RETRY_SLEEP,
        )
        time.sleep(_RETRY_SLEEP)
        try:
            return _build_and_fetch()
        except ResponseError as exc2:
            log.warning("Google Trends second failure for %r: %s — skipping", term, exc2)
            return pd.DataFrame(columns=["interest"])
    except Exception as exc:
        log.error(
            "Unexpected error fetching Google Trends for %r: %s — skipping",
            term,
            exc,
        )
        return pd.DataFrame(columns=["interest"])


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(terms: list[str] | None = None, backfill_from: str | None = None) -> None:
    """Fetch Google Trends weekly interest and write to ArcticDB ``macro`` library.

    Args:
        terms: List of search terms. Defaults to ``DEFAULT_TERMS``
            (4 gold/macro sentiment terms).
        backfill_from: ISO date string (e.g. "2019-01-06"). If set, fetches a
            historical chunk from that date up to (existing_start - 1 day) and
            prepends it. The range must be ≤ 5 years to get weekly granularity;
            if longer, it is split into ≤5yr chunks automatically.
            Note: Google Trends scores are relative within each request window —
            the backfill chunk will have a different scale than current data.
            Normalize at feature-engineering time (z-score recommended).
    """
    settings = get_settings()
    if terms is None:
        terms = list(settings.gtrends_terms)

    store = get_store()

    for i, term in enumerate(terms):
        arc_key = _arc_key(term)

        if backfill_from is not None:
            # --- Backfill mode ---
            existing_start: pd.Timestamp | None = None
            try:
                existing = store.read_series("macro", arc_key)
                if not existing.empty:
                    existing_start = existing.index.min()
            except Exception:
                pass

            # End of backfill = day before existing data (or today if no existing data)
            if existing_start is not None:
                backfill_end = existing_start - pd.Timedelta(days=1)
            else:
                backfill_end = pd.Timestamp.now(tz="UTC").normalize()

            bf_start = pd.Timestamp(backfill_from, tz="UTC")
            if bf_start >= backfill_end:
                log.info("Term %r: backfill range already covered, skipping", term)
            else:
                # Split into ≤5yr chunks (weekly granularity limit)
                chunk_start = bf_start
                chunks: list[pd.DataFrame] = []
                while chunk_start < backfill_end:
                    # Compute chunk end: start + 5yr - 1 day (stay within weekly limit)
                    chunk_end = min(
                        chunk_start + pd.DateOffset(years=_MAX_WEEKLY_YEARS) - pd.Timedelta(days=1),
                        backfill_end,
                    )
                    tf = f"{chunk_start.strftime('%Y-%m-%d')} {chunk_end.strftime('%Y-%m-%d')}"
                    log.info("Term %r: backfill chunk %s", term, tf)
                    df_chunk = _fetch_term_range(term, tf)
                    if not df_chunk.empty:
                        chunks.append(df_chunk)
                    chunk_start = chunk_end + pd.Timedelta(days=1)
                    if chunk_start < backfill_end:
                        log.info("Sleeping %ss before next backfill chunk", _SLEEP_BETWEEN_TERMS)
                        time.sleep(_SLEEP_BETWEEN_TERMS)

                if chunks:
                    df_backfill = pd.concat(chunks)
                    df_backfill = df_backfill[~df_backfill.index.duplicated(keep="last")]
                    df_backfill = df_backfill.sort_index()
                    # Only prepend rows strictly before existing data
                    if existing_start is not None:
                        df_backfill = df_backfill[df_backfill.index < existing_start]
                    if not df_backfill.empty:
                        store.write_series("macro", arc_key, df_backfill)
                        log.info("Backfill: wrote %d rows to macro/%s", len(df_backfill), arc_key)
                    else:
                        log.info("Term %r: no new backfill rows after trim", term)
                else:
                    log.info("Term %r: backfill returned no data", term)
        else:
            # --- Normal incremental mode ---
            df = _fetch_term(term)

            if df.empty:
                log.info("Term %r: no data returned, skipping write", term)
            else:
                store.write_series("macro", arc_key, df)
                log.info("Wrote %d rows to macro/%s", len(df), arc_key)

        if i < len(terms) - 1:
            log.info("Sleeping %ss before next term request", _SLEEP_BETWEEN_TERMS)
            time.sleep(_SLEEP_BETWEEN_TERMS)

    log.info("Google Trends collection complete for %s", terms)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Google Trends retail sentiment collector")
    parser.add_argument(
        "--backfill-from",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Backfill weekly data from this date. Range is split into ≤5yr chunks "
            "to preserve weekly granularity. Only rows before existing data are written."
        ),
    )
    args = parser.parse_args()
    collect(backfill_from=args.backfill_from)
