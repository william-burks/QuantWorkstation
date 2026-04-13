"""
Baker Hughes North America Rig Count collector.

Downloads the weekly North America rig count Excel workbook from Baker Hughes'
public website and writes US and Canada series into the ``macro`` ArcticDB
library via ``store.write_series()``.

Series collected (weekly, keyed on Friday report date):
  - BHI_US_TOTAL_RIGS  : US total rig count
  - BHI_US_OIL_RIGS    : US oil-directed rig count
  - BHI_US_GAS_RIGS    : US gas-directed rig count
  - BHI_CANADA_RIGS    : Canada total rig count

ArcticDB key: as above (e.g. ``BHI_US_TOTAL_RIGS``)
Columns: ``count`` (integer rig count)
Index: UTC DatetimeIndex (weekly, Friday release date)

Incremental: reads last stored date; appends only new rows on subsequent runs.

Run via: ``python -m data.collectors.baker_hughes``
"""

import logging
from datetime import timedelta
from io import BytesIO

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Baker Hughes public Excel download URL for North America rig count
# Updated weekly; no API key required
BHI_NA_EXCEL_URL = (
    "https://rigcount.bakerhughes.com/static-files/7e477ac4-316a-4c7e-a3d2-6e0b7da50dd3"
)

# Sheet name in the workbook containing North America summary data
_NA_SHEET = "North America Rig Count"

# ArcticDB keys for each series
SERIES_KEYS: list[str] = [
    "BHI_US_TOTAL_RIGS",
    "BHI_US_OIL_RIGS",
    "BHI_US_GAS_RIGS",
    "BHI_CANADA_RIGS",
]


# ---------------------------------------------------------------------------
# Download + parse
# ---------------------------------------------------------------------------


def _download_excel(url: str) -> bytes:
    """Download Baker Hughes Excel workbook bytes from *url*.

    Args:
        url: Direct URL to the Excel (.xlsx) file.

    Returns:
        Raw bytes of the Excel file.

    Raises:
        requests.HTTPError: On non-2xx response.
    """
    headers = {
        "User-Agent": ("Mozilla/5.0 (compatible; QuantWorkstation/1.0; +https://github.com/)")
    }
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return bytes(response.content)


def _parse_na_rig_count(excel_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Parse North America rig count from Excel workbook bytes.

    Reads the ``North America Rig Count`` sheet.  Baker Hughes lays out the
    sheet with a header row that contains country/type labels and a ``Date``
    column.  The relevant rows contain:
      - United States: Total, Oil, Gas
      - Canada: Total

    Args:
        excel_bytes: Raw bytes of the Baker Hughes NA Excel workbook.

    Returns:
        Dict mapping ArcticDB key → DataFrame with UTC DatetimeIndex and
        single column ``count`` (int64).

    Raises:
        ValueError: If expected columns or rows are missing from the sheet.
    """
    # Read the sheet; header is on row 0 (default)
    df_raw = pd.read_excel(
        BytesIO(excel_bytes),
        sheet_name=_NA_SHEET,
        engine="openpyxl",
    )

    # Normalize column names: strip whitespace
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Locate the date column (first column, typically labelled "Date")
    date_col = df_raw.columns[0]

    # The sheet has columns: Date, United States Total, United States Oil,
    # United States Gas, Canada Total (plus others we ignore).
    # Column names vary slightly across versions — match case-insensitively.
    col_lower: dict[str, str] = {c.lower(): c for c in df_raw.columns}

    def _find_col(*candidates: str) -> str:
        for candidate in candidates:
            if candidate.lower() in col_lower:
                return col_lower[candidate.lower()]
        raise ValueError(
            f"Cannot find column matching {candidates} in sheet '{_NA_SHEET}'. "
            f"Available: {list(df_raw.columns)}"
        )

    us_total_col = _find_col("United States Total", "U.S. Total", "US Total")
    us_oil_col = _find_col("United States Oil", "U.S. Oil", "US Oil")
    us_gas_col = _find_col("United States Gas", "U.S. Gas", "US Gas")
    canada_col = _find_col("Canada Total", "Canada")

    # Drop rows where the date column is not a valid date (e.g. header repeats,
    # trailing notes)
    df = df_raw[[date_col, us_total_col, us_oil_col, us_gas_col, canada_col]].copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=False)
    df = df.dropna(subset=[date_col])
    df = df.set_index(date_col)
    df.index = df.index.tz_localize("UTC")
    df.index.name = "date"
    df = df.sort_index()

    def _to_count_series(col: pd.Series) -> pd.DataFrame:
        s = pd.to_numeric(col, errors="coerce").dropna().astype("Int64")
        return pd.DataFrame({"count": s})

    return {
        "BHI_US_TOTAL_RIGS": _to_count_series(df[us_total_col]),
        "BHI_US_OIL_RIGS": _to_count_series(df[us_oil_col]),
        "BHI_US_GAS_RIGS": _to_count_series(df[us_gas_col]),
        "BHI_CANADA_RIGS": _to_count_series(df[canada_col]),
    }


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(url: str = BHI_NA_EXCEL_URL) -> None:
    """Download Baker Hughes NA rig count and write to ArcticDB ``macro`` library.

    Incremental: reads the last stored date for each series and appends only
    rows newer than that date.  Safe to run repeatedly — no duplicates.

    Args:
        url: Direct URL to the Baker Hughes NA rig count Excel file.
             Defaults to ``BHI_NA_EXCEL_URL``.
    """
    log.info("Downloading Baker Hughes NA rig count from %s", url)
    excel_bytes = _download_excel(url)
    log.info("Downloaded %d bytes; parsing…", len(excel_bytes))

    series_map = _parse_na_rig_count(excel_bytes)
    store = get_store()

    for arc_key, df_new in series_map.items():
        if df_new.empty:
            log.warning("Series %s: parsed data is empty — skipping", arc_key)
            continue

        # Incremental: find last stored date and filter to new-only rows
        try:
            existing = store.read_series("macro", arc_key)
            if not existing.empty:
                last_date = existing.index.max()
                cutoff = last_date + timedelta(days=1)
                df_new = df_new[df_new.index >= cutoff]
                log.info(
                    "Series %s: last stored %s — %d new rows to append",
                    arc_key,
                    last_date.date(),
                    len(df_new),
                )
        except Exception:
            log.info("Series %s: no existing data — writing full history", arc_key)

        if df_new.empty:
            log.info("Series %s: no new data to write", arc_key)
            continue

        store.write_series("macro", arc_key, df_new)
        log.info("Wrote %d rows to macro/%s", len(df_new), arc_key)

    log.info("Baker Hughes collection complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect()
