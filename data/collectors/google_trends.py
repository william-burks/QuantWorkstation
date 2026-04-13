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


def collect(terms: list[str] | None = None) -> None:
    """Fetch Google Trends weekly interest and write to ArcticDB ``macro`` library.

    Args:
        terms: List of search terms. Defaults to ``DEFAULT_TERMS``
            (4 gold/macro sentiment terms).
    """
    settings = get_settings()
    if terms is None:
        terms = list(settings.gtrends_terms)

    store = get_store()

    for i, term in enumerate(terms):
        arc_key = _arc_key(term)

        df = _fetch_term(term)

        if df.empty:
            log.info("Term %r: no data returned, skipping write", term)
        else:
            # Upsert: overwrite overlapping rows, append new
            try:
                existing = store.read_series("macro", arc_key)
                if not existing.empty:
                    combined = pd.concat([existing, df])
                    # Keep last occurrence per index (new data wins on overlap)
                    combined = combined[~combined.index.duplicated(keep="last")]
                    combined = combined.sort_index()
                    df = combined
            except Exception:
                pass  # No existing data — write fresh

            store.write_series("macro", arc_key, df)
            log.info("Wrote %d rows to macro/%s", len(df), arc_key)

        # Sleep between terms to respect Google's unofficial rate limits
        # (skip sleep after the last term)
        if i < len(terms) - 1:
            log.info("Sleeping %ss before next term request", _SLEEP_BETWEEN_TERMS)
            time.sleep(_SLEEP_BETWEEN_TERMS)

    log.info("Google Trends collection complete for %s", terms)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
