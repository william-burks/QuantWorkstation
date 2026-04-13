"""
USDA NASS Crop Progress collector.

Fetches weekly planting and development stage percentages for corn and soybeans
via the NASS Quick Stats API and writes them into the ``macro`` ArcticDB library
via ``store.write_series()``.

Series collected (ArcticDB key pattern: ``USDA_{CROP}_{STAGE}_{REGION}``):
  Crops: CORN, SOYBEANS
  Stages (corn): PLANTED, EMERGED, SILKING, DOUGH, DENT, MATURE, HARVESTED
  Stages (soybeans): PLANTED, EMERGED, BLOOMING, SETTING_PODS, DROPPING_LEAVES, HARVESTED
  Regions: NATL, IL, IA, IN, NE, MN

  Example: USDA_CORN_PLANTED_NATL, USDA_SOYBEANS_PLANTED_IL

Columns: ``pct`` (float, 0–100)
Index: UTC DatetimeIndex (weekly, Monday release)

Incremental fetch: reads last stored date, requests only newer observations.
Off-season: NASS returns empty results → collector logs INFO and exits cleanly.

Auth: ``USDA_API_KEY`` env var; stored as export in ~/.zshrc per security rules.
Do NOT add to .env.

Run via: ``python -m data.collectors.usda_crop``
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
    "DENT": "PCT DENT",
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
    arc_key: (commodity, unit, state)
    for arc_key, commodity, unit, state in USDA_SERIES
}

DEFAULT_SERIES: list[str] = [arc_key for arc_key, _, _, _ in USDA_SERIES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_series(
    api_key: str,
    arc_key: str,
    start_year: int | None,
) -> pd.DataFrame:
    """Fetch a single USDA NASS crop progress series.

    Args:
        api_key: USDA NASS API key (from USDA_API_KEY env var).
        arc_key: ArcticDB key identifying which series to fetch
            (must be a key in ``_SERIES_MAP``).
        start_year: Year (int) for incremental fetch, or None for full history
            (last 5 years).

    Returns:
        DataFrame with UTC DatetimeIndex and column ``pct`` (float, 0–100).
        Empty DataFrame (with ``pct`` column) if no results (off-season).
    """
    commodity, unit_desc, state_alpha = _SERIES_MAP[arc_key]

    current_year = pd.Timestamp.now(tz="UTC").year
    if start_year is None:
        start_year = current_year - 5

    params: dict[str, str] = {
        "key": api_key,
        "commodity_desc": commodity,
        "statisticcat_desc": "PROGRESS",
        "unit_desc": unit_desc,
        "freq_desc": "WEEKLY",
        "year__GE": str(start_year),
        "format": "JSON",
    }

    if state_alpha is not None:
        params["state_alpha"] = state_alpha

    response = requests.get(NASS_ENDPOINT, params=params, timeout=30)
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


def collect(series: list[str] | None = None) -> None:
    """Fetch USDA NASS crop progress series and write to ArcticDB ``macro`` library.

    Args:
        series: List of ArcticDB keys to collect. Defaults to all corn and soybean
            progress series for national and top-5 states.
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

        # Incremental: find last stored year
        start_year: int | None = None
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_date = existing.index.max()
                # Re-fetch from the year of last stored date (NASS weekly data; week boundaries)
                start_year = (last_date - timedelta(days=7)).year
                log.info(
                    "Series %s: last stored %s, fetching from year %s",
                    arc_key,
                    last_date.date(),
                    start_year,
                )
        except Exception:
            log.info("Series %s: no existing data, fetching full history", arc_key)

        df = _fetch_series(api_key, arc_key, start_year)

        if df.empty:
            log.info("Series %s: no new data (off-season or empty response)", arc_key)
            continue

        # Idempotent merge: if existing data, drop rows already stored
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_stored = existing.index.max()
                df = df[df.index > last_stored]
        except Exception:
            pass  # no existing data — write full fetch

        if df.empty:
            log.info("Series %s: no new rows after dedup", arc_key)
            continue

        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("USDA crop progress collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
