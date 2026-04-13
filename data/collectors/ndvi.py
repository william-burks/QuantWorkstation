"""
NASA AppEEARS NDVI crop health collector.

Requests server-side spatial subsets for US corn belt regions via the
AppEEARS REST API, receives CSV output (no rasterio dependency), computes
mean NDVI per region, derives an anomaly signal (deviation from 5-year daily
historical average), and writes results into the shared ``macro`` ArcticDB
library via ``store.write_series()``.

Series written per region (ArcticDB key pattern: ``NDVI_{REGION}_1D``):
  Columns: ``ndvi`` (float, 0–1), ``ndvi_anomaly`` (float, signed deviation)

Climatology baseline (ArcticDB key pattern: ``NDVI_{REGION}_CLIM_1D``):
  Columns: ``ndvi_mean`` (float, 5-year daily mean by day-of-year)

Regions:
  CORN_BELT, IOWA, ILLINOIS, INDIANA, NEBRASKA, MINNESOTA

Auth:
  NASA Earthdata Bearer token from AppEEARS login.
  ``NASA_EARTHDATA_TOKEN`` env var; stored as export in ~/.zshrc per security rules.
  Do NOT add to .env.

Off-season (November–March): collector logs INFO and exits cleanly — no write.

Run via: ``python -m data.collectors.ndvi``
"""

import io
import logging
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests  # type: ignore[import-untyped]

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APPEEARS_BASE = "https://appeears.earthdatacloud.nasa.gov/api"
APPEEARS_LOGIN = f"{APPEEARS_BASE}/login"
APPEEARS_TASK = f"{APPEEARS_BASE}/task"
APPEEARS_BUNDLE = f"{APPEEARS_BASE}/bundle"

# MODIS Terra Vegetation Indices 16-day 250m
MODIS_PRODUCT = "MOD13Q1.061"
MODIS_LAYER = "_250m_16_days_NDVI"

# Growing season: April–October (months 4–10)
GROWING_SEASON_START_MONTH = 4
GROWING_SEASON_END_MONTH = 10

# Off-season months (November–March)
OFF_SEASON_MONTHS = {11, 12, 1, 2, 3}

# Climatology baseline years
CLIM_YEARS = 5

# Polling config
POLL_INTERVAL_SECONDS = 30
POLL_MAX_ATTEMPTS = 120  # 60 minutes max

# Region bounding boxes: (lat_min, lon_min, lat_max, lon_max)
# Corn Belt aggregate uses Iowa bounding box extended; state boxes are tighter.
REGION_BBOX: dict[str, tuple[float, float, float, float]] = {
    "CORN_BELT": (36.5, -104.0, 48.5, -80.5),
    "IOWA": (40.35, -96.65, 43.5, -90.1),
    "ILLINOIS": (36.97, -91.5, 42.51, -87.02),
    "INDIANA": (37.77, -88.1, 41.77, -84.78),
    "NEBRASKA": (39.99, -104.05, 43.0, -95.31),
    "MINNESOTA": (43.49, -97.24, 49.38, -89.48),
}

REGIONS: list[str] = list(REGION_BBOX.keys())


# ---------------------------------------------------------------------------
# Off-season guard
# ---------------------------------------------------------------------------


def _is_off_season(check_date: date | None = None) -> bool:
    """Return True if check_date falls in the November–March off-season."""
    if check_date is None:
        check_date = date.today()
    return check_date.month in OFF_SEASON_MONTHS


# ---------------------------------------------------------------------------
# AppEEARS auth
# ---------------------------------------------------------------------------


def _get_bearer_token(earthdata_token: str) -> str:
    """Exchange NASA Earthdata token for AppEEARS Bearer token.

    Args:
        earthdata_token: NASA Earthdata API token from NASA_EARTHDATA_TOKEN env var.

    Returns:
        AppEEARS Bearer token string.

    Raises:
        requests.HTTPError: If login fails.
    """
    resp = requests.post(
        APPEEARS_LOGIN,
        headers={"Authorization": f"Bearer {earthdata_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    token: str = resp.json()["token"]
    return token


# ---------------------------------------------------------------------------
# Task submission + polling
# ---------------------------------------------------------------------------


def _build_task_payload(
    region: str,
    start_date: str,
    end_date: str,
    task_name: str,
) -> dict[str, object]:
    """Build AppEEARS area task payload for a region.

    Args:
        region: Region key (must be in REGION_BBOX).
        start_date: ISO date string ``YYYY-MM-DD``.
        end_date: ISO date string ``YYYY-MM-DD``.
        task_name: Unique name for the AppEEARS task.

    Returns:
        JSON-serialisable dict for POST /api/task.
    """
    lat_min, lon_min, lat_max, lon_max = REGION_BBOX[region]
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon_min, lat_min],
                            [lon_max, lat_min],
                            [lon_max, lat_max],
                            [lon_min, lat_max],
                            [lon_min, lat_min],
                        ]
                    ],
                },
                "properties": {"id": region},
            }
        ],
    }
    return {
        "task_type": "area",
        "task_name": task_name,
        "params": {
            "dates": [{"startDate": start_date, "endDate": end_date}],
            "layers": [{"product": MODIS_PRODUCT, "layer": MODIS_LAYER}],
            "output": {"format": {"type": "csv"}, "projection": {"name": "geographic"}},
            "geo": geojson,
        },
    }


def _submit_task(bearer_token: str, payload: dict[str, object]) -> str:
    """Submit an AppEEARS task and return the task_id.

    Args:
        bearer_token: AppEEARS Bearer token.
        payload: Task payload dict from ``_build_task_payload``.

    Returns:
        task_id string.

    Raises:
        requests.HTTPError: If submission fails.
    """
    resp = requests.post(
        APPEEARS_TASK,
        json=payload,
        headers={"Authorization": f"Bearer {bearer_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    task_id: str = resp.json()["task_id"]
    return task_id


def _poll_task(bearer_token: str, task_id: str) -> str:
    """Poll AppEEARS task until status is ``done`` or ``error``.

    Args:
        bearer_token: AppEEARS Bearer token.
        task_id: Task ID returned by ``_submit_task``.

    Returns:
        Final status string (``done`` or ``error``).

    Raises:
        TimeoutError: If task does not complete within POLL_MAX_ATTEMPTS.
    """
    for attempt in range(POLL_MAX_ATTEMPTS):
        resp = requests.get(
            f"{APPEEARS_TASK}/{task_id}",
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        status: str = resp.json().get("status", "unknown")
        log.debug("Task %s status: %s (attempt %d)", task_id, status, attempt + 1)
        if status in ("done", "error"):
            return status
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"AppEEARS task {task_id} did not complete within "
        f"{POLL_MAX_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
    )


# ---------------------------------------------------------------------------
# Bundle download + CSV parse
# ---------------------------------------------------------------------------


def _download_bundle_csv(bearer_token: str, task_id: str) -> pd.DataFrame:
    """Download the first CSV file from an AppEEARS task bundle and parse it.

    AppEEARS returns a bundle with one or more files. The primary CSV contains
    columns including ``Date`` and a layer column (the MODIS NDVI layer name).
    Pixel values are averaged to produce regional mean NDVI.

    Args:
        bearer_token: AppEEARS Bearer token.
        task_id: Completed AppEEARS task ID.

    Returns:
        DataFrame with UTC DatetimeIndex and column ``ndvi`` (float, 0–1 scale).
        Empty DataFrame (with ``ndvi`` column) if no data found.

    Raises:
        requests.HTTPError: If bundle fetch fails.
        ValueError: If expected columns not found in CSV.
    """
    # List bundle files
    resp = requests.get(
        f"{APPEEARS_BUNDLE}/{task_id}",
        headers={"Authorization": f"Bearer {bearer_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json().get("files", [])

    # Find the primary CSV (not QC or metadata)
    csv_files = [
        f for f in files
        if f.get("file_name", "").endswith(".csv")
        and "_QC" not in f.get("file_name", "")
    ]
    if not csv_files:
        log.warning("No CSV files found in bundle for task %s", task_id)
        return pd.DataFrame(columns=["ndvi"])

    file_id = csv_files[0]["file_id"]
    dl_resp = requests.get(
        f"{APPEEARS_BUNDLE}/{task_id}/{file_id}",
        headers={"Authorization": f"Bearer {bearer_token}"},
        timeout=120,
        stream=True,
    )
    dl_resp.raise_for_status()

    raw_csv = dl_resp.content.decode("utf-8")
    df = pd.read_csv(io.StringIO(raw_csv))

    # AppEEARS CSV columns vary by layer name; find NDVI column
    # Layer column: typically the layer name without leading underscore
    ndvi_col = None
    for col in df.columns:
        if "NDVI" in col.upper():
            ndvi_col = col
            break

    if ndvi_col is None:
        raise ValueError(
            f"NDVI column not found in AppEEARS CSV for task {task_id}. "
            f"Columns: {list(df.columns)}"
        )

    # Date column
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    result = df[[date_col, ndvi_col]].copy()
    result = result.rename(columns={date_col: "date", ndvi_col: "raw_ndvi"})
    result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce")
    result = result.dropna(subset=["date"])
    result["raw_ndvi"] = pd.to_numeric(result["raw_ndvi"], errors="coerce")

    # MODIS NDVI is stored as integer × 0.0001 in AppEEARS CSV — scale to 0–1
    # Values outside valid range (-2000 to 10000 raw → -0.2 to 1.0) are fill values
    result["raw_ndvi"] = result["raw_ndvi"].where(
        result["raw_ndvi"].between(-2000, 10000)
    )
    result["raw_ndvi"] = result["raw_ndvi"] * 0.0001
    result = result.dropna(subset=["raw_ndvi"])

    # Mean NDVI per day (aggregate across pixels)
    daily = result.groupby("date")["raw_ndvi"].mean().rename("ndvi")
    daily = daily.sort_index()
    return daily.to_frame()


# ---------------------------------------------------------------------------
# Climatology
# ---------------------------------------------------------------------------


def _compute_climatology(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 5-year daily climatology (mean NDVI by day-of-year).

    Args:
        df: DataFrame with UTC DatetimeIndex and ``ndvi`` column.

    Returns:
        DataFrame indexed by day-of-year (1–366) with column ``ndvi_mean``.
    """
    df = df.copy()
    df["doy"] = df.index.day_of_year
    clim = df.groupby("doy")["ndvi"].mean().rename("ndvi_mean")
    return clim.to_frame()


def _compute_anomaly(df: pd.DataFrame, clim: pd.DataFrame) -> pd.DataFrame:
    """Add ``ndvi_anomaly`` column: deviation from climatology for same day-of-year.

    Args:
        df: DataFrame with UTC DatetimeIndex and ``ndvi`` column.
        clim: Climatology DataFrame indexed by day-of-year with ``ndvi_mean`` column.

    Returns:
        DataFrame with ``ndvi`` and ``ndvi_anomaly`` columns.
    """
    df = df.copy()
    doy = df.index.day_of_year
    mean_values = np.array([clim.loc[d, "ndvi_mean"] if d in clim.index else np.nan for d in doy])
    df["ndvi_anomaly"] = df["ndvi"].values - mean_values
    return df[["ndvi", "ndvi_anomaly"]]


# ---------------------------------------------------------------------------
# Per-region collection
# ---------------------------------------------------------------------------


def _collect_region(
    bearer_token: str,
    region: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Submit AppEEARS task for a region, poll, download, and return parsed DataFrame.

    Args:
        bearer_token: AppEEARS Bearer token.
        region: Region key (must be in REGION_BBOX).
        start_date: ISO date string for task start.
        end_date: ISO date string for task end.

    Returns:
        DataFrame with UTC DatetimeIndex and column ``ndvi`` (float, 0–1).
        Empty DataFrame (with ``ndvi`` column) on failure.
    """
    task_name = f"qws_ndvi_{region}_{start_date}_{end_date}"
    payload = _build_task_payload(region, start_date, end_date, task_name)

    log.info("Submitting AppEEARS task for region %s (%s → %s)", region, start_date, end_date)
    task_id = _submit_task(bearer_token, payload)
    log.info("Task %s submitted for region %s — polling...", task_id, region)

    status = _poll_task(bearer_token, task_id)
    if status != "done":
        log.error("AppEEARS task %s for region %s ended with status: %s", task_id, region, status)
        return pd.DataFrame(columns=["ndvi"])

    log.info("Task %s done — downloading CSV for region %s", task_id, region)
    return _download_bundle_csv(bearer_token, task_id)


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(regions: list[str] | None = None) -> None:
    """Fetch NASA AppEEARS NDVI and write to ArcticDB ``macro`` library.

    Off-season guard: if today is November–March, logs INFO and returns immediately.

    For each region:
    1. Read existing data to determine incremental start date.
    2. Submit AppEEARS task, poll until done, download CSV.
    3. Compute/update 5-year climatology baseline.
    4. Compute anomaly (NDVI − climatology for same day-of-year).
    5. Write ``NDVI_{REGION}_1D`` series (ndvi, ndvi_anomaly columns).
    6. Write ``NDVI_{REGION}_CLIM_1D`` series (ndvi_mean indexed by day-of-year).

    Args:
        regions: List of region keys to collect. Defaults to all 6 regions.
    """
    if _is_off_season():
        log.info("NDVI collector: off-season (Nov–Mar) — no-op, exiting cleanly")
        return

    if regions is None:
        regions = list(REGIONS)

    settings = get_settings()
    earthdata_token = settings.nasa_earthdata_token
    store = get_store()

    bearer_token = _get_bearer_token(earthdata_token)

    today = date.today()
    end_date = today.strftime("%Y-%m-%d")

    for region in regions:
        if region not in REGION_BBOX:
            log.warning("Unknown NDVI region key %s — skipping", region)
            continue

        arc_key = f"NDVI_{region}_1D"
        clim_key = f"NDVI_{region}_CLIM_1D"

        # Determine fetch window
        start_date: str
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_date = existing.index.max().date()
                start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                log.info(
                    "Region %s: last stored %s, fetching from %s",
                    region, last_date, start_date,
                )
            else:
                clim_start = (today - timedelta(days=365 * CLIM_YEARS)).strftime("%Y-%m-%d")
                start_date = clim_start
                log.info("Region %s: no existing data, fetching 5-year baseline from %s", region, start_date)
        except Exception:
            clim_start = (today - timedelta(days=365 * CLIM_YEARS)).strftime("%Y-%m-%d")
            start_date = clim_start
            log.info("Region %s: no existing data, fetching 5-year baseline from %s", region, start_date)

        df_new = _collect_region(bearer_token, region, start_date, end_date)

        if df_new.empty:
            log.info("Region %s: no new data to write", region)
            continue

        # Merge with existing for climatology computation
        df_all = df_new.copy()
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                df_all = pd.concat([existing[["ndvi"]], df_new]).sort_index()
                df_all = df_all[~df_all.index.duplicated(keep="last")]
        except Exception:
            pass

        # Compute / refresh climatology
        clim = _compute_climatology(df_all)
        store.write_series("macro", clim_key, clim)
        log.info("Wrote climatology to macro/%s (%d day-of-year entries)", clim_key, len(clim))

        # Compute anomaly for new data only
        df_new = _compute_anomaly(df_new, clim)

        # Idempotent merge: drop rows already stored
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_stored = existing.index.max()
                df_new = df_new[df_new.index > last_stored]
        except Exception:
            pass

        if df_new.empty:
            log.info("Region %s: no new rows after dedup", region)
            continue

        store.write_series("macro", arc_key, df_new)
        log.info("Wrote %d rows to macro/%s", len(df_new), arc_key)

    log.info("NDVI collection complete for regions: %s", regions)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
