"""
USDA NASS Crop Progress and Condition collector.

Fetches weekly planting/development stage percentages AND crop condition ratings
for corn and soybeans via the NASS Quick Stats API, writing into the ``macro``
ArcticDB library via ``store.write_series()``.

Progress series (ArcticDB key pattern: ``USDA_{CROP}_{STAGE}_{REGION}``):
  Crops: CORN, SOYBEANS
  Stages (corn): PLANTED, EMERGED, SILKING, DOUGH, DENT, MATURE, HARVESTED
  Stages (soybeans): PLANTED, EMERGED, BLOOMING, SETTING_PODS, DROPPING_LEAVES, HARVESTED
  Regions: NATL, IL, IA, IN, NE, MN

Condition series (ArcticDB key pattern: ``USDA_{CROP}_COND_{RATING}_{REGION}``):
  Crops: CORN, SOYBEANS
  Ratings: EXCELLENT, GOOD, FAIR, POOR, VERY_POOR
  Regions: NATL, IL, IA, IN, NE, MN

  Example: USDA_CORN_COND_EXCELLENT_NATL, USDA_SOYBEANS_COND_GOOD_IL

Columns: ``pct`` (float, 0–100)
Index: UTC DatetimeIndex (weekly, Monday release)

Incremental fetch: reads last stored date, requests only newer observations.
Off-season: NASS returns empty results → collector logs INFO and exits cleanly.

Auth: ``USDA_API_KEY`` env var; stored as export in ~/.zshrc per security rules.
Do NOT add to .env.

Run via: ``python -m data.collectors.usda_crop``
"""

import logging
import time
from datetime import timedelta

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NASS_ENDPOINT = "https://quickstats.nass.usda.gov/api/api_GET/"

# Top-5 producing states + national
REGIONS: list[str] = ["NATL", "IL", "IA", "IN", "NE", "MN"]

# State alpha codes for NASS (NATL = no state_alpha param)
_STATE_MAP: dict[str, str | None] = {
    "NATL": None,
    "IL": "IL",
    "IA": "IA",
    "IN": "IN",
    "NE": "NE",
    "MN": "MN",
}

# Corn stages and their NASS unit_desc values
CORN_STAGES: dict[str, str] = {
    "PLANTED": "PCT PLANTED",
    "EMERGED": "PCT EMERGED",
    "SILKING": "PCT SILKING",
    "DOUGH": "PCT DOUGH",
    "DENT": "PCT DENTED",
    "MATURE": "PCT MATURE",
    "HARVESTED": "PCT HARVESTED",
}

# Soybean stages and their NASS unit_desc values
SOYBEAN_STAGES: dict[str, str] = {
    "PLANTED": "PCT PLANTED",
    "EMERGED": "PCT EMERGED",
    "BLOOMING": "PCT BLOOMING",
    "SETTING_PODS": "PCT SETTING PODS",
    "DROPPING_LEAVES": "PCT DROPPING LEAVES",
    "HARVESTED": "PCT HARVESTED",
}


# All series as (arc_key, commodity_desc, unit_desc, state_alpha | None)
def _build_series_list() -> list[tuple[str, str, str, str | None]]:
    series: list[tuple[str, str, str, str | None]] = []
    for region in REGIONS:
        state = _STATE_MAP[region]
        for stage_key, unit_desc in CORN_STAGES.items():
            arc_key = f"USDA_CORN_{stage_key}_{region}"
            series.append((arc_key, "CORN", unit_desc, state))
        for stage_key, unit_desc in SOYBEAN_STAGES.items():
            arc_key = f"USDA_SOYBEANS_{stage_key}_{region}"
            series.append((arc_key, "SOYBEANS", unit_desc, state))
    return series


USDA_SERIES: list[tuple[str, str, str, str | None]] = _build_series_list()

# Lookup from arc_key → (commodity_desc, unit_desc, state_alpha | None)
_SERIES_MAP: dict[str, tuple[str, str, str | None]] = {
    arc_key: (commodity, unit, state) for arc_key, commodity, unit, state in USDA_SERIES
}

DEFAULT_SERIES: list[str] = [arc_key for arc_key, _, _, _ in USDA_SERIES]


# ---------------------------------------------------------------------------
# Condition series
# ---------------------------------------------------------------------------

CORN_CONDITIONS: dict[str, str] = {
    "EXCELLENT": "PCT EXCELLENT",
    "GOOD": "PCT GOOD",
    "FAIR": "PCT FAIR",
    "POOR": "PCT POOR",
    "VERY_POOR": "PCT VERY POOR",
}

SOYBEAN_CONDITIONS: dict[str, str] = {
    "EXCELLENT": "PCT EXCELLENT",
    "GOOD": "PCT GOOD",
    "FAIR": "PCT FAIR",
    "POOR": "PCT POOR",
    "VERY_POOR": "PCT VERY POOR",
}


def _build_condition_series_list() -> list[tuple[str, str, str, str | None]]:
    series: list[tuple[str, str, str, str | None]] = []
    for region in REGIONS:
        state = _STATE_MAP[region]
        for rating_key, unit_desc in CORN_CONDITIONS.items():
            arc_key = f"USDA_CORN_COND_{rating_key}_{region}"
            series.append((arc_key, "CORN", unit_desc, state))
        for rating_key, unit_desc in SOYBEAN_CONDITIONS.items():
            arc_key = f"USDA_SOYBEANS_COND_{rating_key}_{region}"
            series.append((arc_key, "SOYBEANS", unit_desc, state))
    return series


USDA_CONDITION_SERIES: list[tuple[str, str, str, str | None]] = _build_condition_series_list()

_CONDITION_SERIES_MAP: dict[str, tuple[str, str, str | None]] = {
    arc_key: (commodity, unit, state) for arc_key, commodity, unit, state in USDA_CONDITION_SERIES
}

DEFAULT_CONDITION_SERIES: list[str] = [arc_key for arc_key, _, _, _ in USDA_CONDITION_SERIES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_series(
    api_key: str,
    arc_key: str,
    start_year: int | None,
    series_map: dict[str, tuple[str, str, str | None]] | None = None,
    statisticcat_desc: str = "PROGRESS",
) -> pd.DataFrame:
    """Fetch a single USDA NASS crop progress or condition series.

    Args:
        api_key: USDA NASS API key (from USDA_API_KEY env var).
        arc_key: ArcticDB key identifying which series to fetch.
        start_year: Year (int) for incremental fetch, or None for full history
            (last 5 years).
        series_map: Lookup dict for arc_key → (commodity, unit_desc, state_alpha).
            Defaults to ``_SERIES_MAP`` (progress series).
        statisticcat_desc: NASS category (``"PROGRESS"`` or ``"CONDITION"``).

    Returns:
        DataFrame with UTC DatetimeIndex and column ``pct`` (float, 0–100).
        Empty DataFrame (with ``pct`` column) if no results (off-season).
    """
    if series_map is None:
        series_map = _SERIES_MAP
    commodity, unit_desc, state_alpha = series_map[arc_key]

    current_year = pd.Timestamp.now(tz="UTC").year
    if start_year is None:
        start_year = current_year - 5

    params: dict[str, str] = {
        "key": api_key,
        "commodity_desc": commodity,
        "statisticcat_desc": statisticcat_desc,
        "unit_desc": unit_desc,
        "freq_desc": "WEEKLY",
        "year__GE": str(start_year),
        "format": "JSON",
    }

    if state_alpha is not None:
        params["state_alpha"] = state_alpha

    for attempt in range(3):
        response = requests.get(NASS_ENDPOINT, params=params, timeout=30)
        if response.status_code == 403:
            wait = 60 * (attempt + 1)
            log.warning("NASS rate limit (403) — waiting %ds before retry %d/3", wait, attempt + 1)
            time.sleep(wait)
            continue
        response.raise_for_status()
        break
    else:
        response.raise_for_status()

    payload = response.json()
    rows = payload.get("data", [])

    if not rows:
        return pd.DataFrame(columns=["pct"])

    df = pd.DataFrame(rows)
    # NASS returns week_ending as "YYYY-MM-DD" and Value as string (may include "(D)" for suppressed)
    df = df[["week_ending", "Value"]].copy()
    df = df.rename(columns={"week_ending": "date", "Value": "pct"})
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date")
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df = df.dropna(subset=["pct"])
    df = df.sort_index()
    return df


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(series: list[str] | None = None, force_start_year: int | None = None) -> None:
    """Fetch USDA NASS crop progress series and write to ArcticDB ``macro`` library.

    Args:
        series: List of ArcticDB keys to collect. Defaults to all corn and soybean
            progress series for national and top-5 states.
        force_start_year: If set, fetch from this year regardless of existing data.
            Use for historical backfills (e.g. force_start_year=2019). Only rows
            before the existing data start are written; existing data is never
            overwritten.
    """
    settings = get_settings()
    if series is None:
        series = list(DEFAULT_SERIES)

    api_key = settings.usda_api_key
    store = get_store()

    for arc_key in series:
        if arc_key not in _SERIES_MAP:
            log.warning("Unknown USDA series key %s — skipping", arc_key)
            continue

        # Determine fetch start year and existing data bounds
        start_year: int | None = None
        existing_start: pd.Timestamp | None = None
        existing_end: pd.Timestamp | None = None
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                existing_start = existing.index.min()
                existing_end = existing.index.max()
                if force_start_year is not None:
                    start_year = force_start_year
                    log.info("Series %s: force backfill from %s", arc_key, force_start_year)
                else:
                    start_year = (existing_end - timedelta(days=7)).year
                    log.info(
                        "Series %s: last stored %s, fetching from year %s",
                        arc_key,
                        existing_end.date(),
                        start_year,
                    )
        except Exception:
            log.info("Series %s: no existing data, fetching full history", arc_key)

        df = _fetch_series(api_key, arc_key, start_year)
        time.sleep(1.5)  # stay well under NASS rate limit (~40 req/min)

        if df.empty:
            log.info("Series %s: no new data (off-season or empty response)", arc_key)
            continue

        # Trim to relevant rows only
        if force_start_year is not None and existing_start is not None:
            # Backfill: only prepend rows before existing data (existing wins on overlap)
            df = df[df.index < existing_start]
        elif existing_end is not None:
            # Incremental: only keep rows after last stored
            df = df[df.index > existing_end]

        if df.empty:
            log.info("Series %s: no new rows after dedup", arc_key)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("USDA crop progress collection complete")


def collect_condition(series: list[str] | None = None, force_start_year: int | None = None) -> None:
    """Fetch USDA NASS crop condition ratings and write to ArcticDB ``macro`` library.

    Collects weekly Good/Excellent/Fair/Poor/Very Poor percentages for corn and
    soybeans. These are the market-moving condition numbers watched by grain traders.

    Args:
        series: List of ArcticDB keys to collect. Defaults to all condition
            series for corn and soybeans across national and top-5 states.
        force_start_year: If set, fetch from this year regardless of existing data.
            Only rows before the existing data start are written.
    """
    settings = get_settings()
    if series is None:
        series = list(DEFAULT_CONDITION_SERIES)

    api_key = settings.usda_api_key
    store = get_store()

    for arc_key in series:
        if arc_key not in _CONDITION_SERIES_MAP:
            log.warning("Unknown USDA condition series key %s — skipping", arc_key)
            continue

        start_year: int | None = None
        existing_start: pd.Timestamp | None = None
        existing_end: pd.Timestamp | None = None
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                existing_start = existing.index.min()
                existing_end = existing.index.max()
                if force_start_year is not None:
                    start_year = force_start_year
                    log.info("Condition %s: force backfill from %s", arc_key, force_start_year)
                else:
                    start_year = (existing_end - timedelta(days=7)).year
                    log.info(
                        "Condition %s: last stored %s, fetching from year %s",
                        arc_key,
                        existing_end.date(),
                        start_year,
                    )
        except Exception:
            log.info("Condition %s: no existing data, fetching full history", arc_key)

        df = _fetch_series(
            api_key,
            arc_key,
            start_year,
            series_map=_CONDITION_SERIES_MAP,
            statisticcat_desc="CONDITION",
        )
        time.sleep(1.5)

        if df.empty:
            log.info("Condition %s: no new data (off-season or empty response)", arc_key)
            continue

        if force_start_year is not None and existing_start is not None:
            df = df[df.index < existing_start]
        elif existing_end is not None:
            df = df[df.index > existing_end]

        if df.empty:
            log.info("Condition %s: no new rows after dedup", arc_key)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("USDA crop condition collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="USDA NASS crop progress + condition collector")
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        metavar="YEAR",
        help="Force backfill from this year (e.g. 2019). Prepends rows before existing data.",
    )
    args = parser.parse_args()
    collect(force_start_year=args.start_year)
    collect_condition(force_start_year=args.start_year)
