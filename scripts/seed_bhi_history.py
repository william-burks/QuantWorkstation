"""
Seed BHI historical data from local Excel archive files.

Run once after downloading the archive files from Baker Hughes:
  python scripts/seed_bhi_history.py

Files expected in ~/Downloads/:
  - 08-29-2025 North America Rig Count Report (1).xlsx  (NA weekly detail 2013-Aug 2025)
  - 04-10-2026 North_America Rig_Count Report (2).xlsx  (NA weekly detail 2024-Apr 2026 — has state breakdown)
  - July-2025  WorldWide Rig Count Report.xlsx          (WW monthly detail 2013-Jul 2025)
  - March-2026  WorldWide Rig Count Report.xlsx         (WW snapshot Mar 2026)
  - Rigs by State_Jan 2000_Mar 2024.xlsx                (US weekly by state 2000-Mar 2024)
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.store import get_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DOWNLOADS = Path.home() / "Downloads"

# ---------------------------------------------------------------------------
# Key state row labels → ArcticDB key
# States with Land/Offshore breakdown have a "TOTAL X" row.
# Single-segment states appear as a bare label (sometimes abbreviated).
# ---------------------------------------------------------------------------
KEY_STATE_LABELS: dict[str, str] = {
    "TOTAL TEXAS": "BHI_STATE_TX_RIGS",  # Permian Basin + Eagle Ford
    "NEW MEXICO": "BHI_STATE_NM_RIGS",  # Permian Basin
    "N DAKOTA": "BHI_STATE_ND_RIGS",  # Bakken
    "TOTAL LOUISIANA": "BHI_STATE_LA_RIGS",  # Haynesville + Gulf offshore
    "OKLAHOMA": "BHI_STATE_OK_RIGS",  # SCOOP/STACK
    "PENNSYLVANIA": "BHI_STATE_PA_RIGS",  # Marcellus/Utica
    "W VIRGINIA": "BHI_STATE_WV_RIGS",  # Marcellus/Utica
    "WYOMING": "BHI_STATE_WY_RIGS",  # DJ Basin / Niobrara
    "COLORADO": "BHI_STATE_CO_RIGS",  # DJ Basin
}

# State names as they appear in the NAM Weekly sheet State/Province column
NAM_WEEKLY_STATE_MAP: dict[str, str] = {
    "TEXAS": "BHI_STATE_TX_RIGS",
    "NEW MEXICO": "BHI_STATE_NM_RIGS",
    "NORTH DAKOTA": "BHI_STATE_ND_RIGS",
    "LOUISIANA": "BHI_STATE_LA_RIGS",
    "OKLAHOMA": "BHI_STATE_OK_RIGS",
    "PENNSYLVANIA": "BHI_STATE_PA_RIGS",
    "WEST VIRGINIA": "BHI_STATE_WV_RIGS",
    "WYOMING": "BHI_STATE_WY_RIGS",
    "COLORADO": "BHI_STATE_CO_RIGS",
}


# ---------------------------------------------------------------------------
# 1. WW Monthly detail — 2013-Jul 2025 monthly
# ---------------------------------------------------------------------------


def seed_ww_monthly(path: Path) -> None:
    log.info("Seeding WW monthly history from %s", path.name)
    df = pd.read_excel(path, sheet_name="WW Monthly", engine="openpyxl", header=11)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[["Region", "Year", "Month", "Rig Count Value"]].dropna(subset=["Region"])
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Month"] = pd.to_numeric(df["Month"], errors="coerce")
    df["Rig Count Value"] = pd.to_numeric(df["Rig Count Value"], errors="coerce")
    df = df.dropna()
    df["date"] = pd.to_datetime(
        df["Year"].astype(int).astype(str) + "-" + df["Month"].astype(int).astype(str) + "-01",
        utc=True,
    )

    # Aggregate: sum all sub-types per region per month
    regional = df.groupby(["Region", "date"])["Rig Count Value"].sum().reset_index()

    regions = {
        "Africa": "BHI_WW_AFRICA_RIGS",
        "Asia-Pacific": "BHI_WW_APAC_RIGS",
        "Europe": "BHI_WW_EUROPE_RIGS",
        "Latin America": "BHI_WW_LATAM_RIGS",
        "Middle East": "BHI_WW_MIDEAST_RIGS",
        "North America": "BHI_WW_NA_RIGS",
    }

    store = get_store()
    region_dfs: dict[str, pd.DataFrame] = {}

    for region_label, arc_key in regions.items():
        sub = regional[regional["Region"] == region_label][["date", "Rig Count Value"]].copy()
        sub = sub.set_index("date").rename(columns={"Rig Count Value": "count"})
        sub = sub.sort_index()
        region_dfs[region_label] = sub
        store.write_series("macro", arc_key, sub)
        log.info("Wrote %d rows to macro/%s", len(sub), arc_key)

    # International = all regions except North America
    intl_regions = [r for r in regions if r != "North America"]
    intl = (
        regional[regional["Region"].isin(intl_regions)]
        .groupby("date")["Rig Count Value"]
        .sum()
        .rename("count")
        .to_frame()
    )
    store.write_series("macro", "BHI_WW_INTL_RIGS", intl)
    log.info("Wrote %d rows to macro/BHI_WW_INTL_RIGS", len(intl))

    # Worldwide = all regions
    ww = regional.groupby("date")["Rig Count Value"].sum().rename("count").to_frame()
    store.write_series("macro", "BHI_WW_TOTAL_RIGS", ww)
    log.info("Wrote %d rows to macro/BHI_WW_TOTAL_RIGS", len(ww))

    # US and Canada come from the North America region in WW detail —
    # we don't have country-level breakdown in this file so skip BHI_WW_US/CANADA here
    log.info("WW monthly seeding complete")


# ---------------------------------------------------------------------------
# 2. Snapshots (NA archive Aug-2025 and WW archive Jul-2025 / Mar-2026)
#    Reuse the existing parse functions from the collector
# ---------------------------------------------------------------------------


def seed_snapshots() -> None:
    from data.collectors.baker_hughes import (
        _parse_na_rig_count,
        _parse_ww_rig_count,
    )

    store = get_store()

    snapshot_files = [
        (DOWNLOADS / "08-29-2025 North America Rig Count Report.xlsx", "na"),
        (DOWNLOADS / "July-2025  WorldWide Rig Count Report.xlsx", "ww"),
        (DOWNLOADS / "March-2026  WorldWide Rig Count Report.xlsx", "ww"),
    ]

    for path, kind in snapshot_files:
        if not path.exists():
            log.warning("Snapshot not found: %s — skipping", path.name)
            continue
        log.info("Seeding snapshot from %s", path.name)
        excel_bytes = path.read_bytes()
        parser = _parse_na_rig_count if kind == "na" else _parse_ww_rig_count
        try:
            series_map = parser(excel_bytes)
        except Exception as e:
            log.error("Parse failed for %s: %s", path.name, e)
            continue
        for arc_key, df_new in series_map.items():
            store.write_series("macro", arc_key, df_new)
            log.info("Wrote %d rows to macro/%s", len(df_new), arc_key)


# ---------------------------------------------------------------------------
# 3. State file — US weekly 2000-2024
# ---------------------------------------------------------------------------


def _parse_state_sheet(xl: pd.ExcelFile, sheet: str) -> dict[str, pd.Series]:
    """Parse one month-sheet from Rigs by State.

    Returns dict: arc_key → pd.Series(count, index=UTC DatetimeIndex).
    Dates are at row 4 (0-indexed), odd columns (1, 3, 5, ...).
    Values for each state/total row are at same odd columns.
    """
    df = xl.parse(sheet, header=None)
    if df.shape[0] < 5:
        return {}

    # Row 4 (0-indexed) has weekly dates at odd column positions
    date_row = df.iloc[4]
    date_cols = []
    for col_idx, val in enumerate(date_row):
        if pd.notna(val) and not isinstance(val, str):
            try:
                ts = pd.Timestamp(val)
                if ts.year > 1990:
                    date_cols.append((col_idx, ts))
            except Exception:
                pass

    if not date_cols:
        return {}

    # Build label → row-index map
    label_to_row: dict[str, int] = {}
    for row_idx in range(5, len(df)):
        label = str(df.iloc[row_idx, 0]).strip().upper()
        if label and label != "NAN":
            label_to_row[label] = row_idx

    targets: dict[str, str] = {
        "TOTAL UNITED STATES": "BHI_STATE_US_RIGS",
        "TOTAL CANADA": "BHI_STATE_CANADA_RIGS",
        **KEY_STATE_LABELS,
    }

    result: dict[str, pd.Series] = {}
    for label, arc_key in targets.items():
        label_stripped = label.strip()
        # find matching row (leading spaces in sheet)
        match_idx: int | None = None
        for k, v in label_to_row.items():
            if k.strip() == label_stripped:
                match_idx = v
                break
        if match_idx is None:
            continue
        data_row = df.iloc[match_idx]
        timestamps = []
        values = []
        for col_idx, ts in date_cols:
            raw = data_row.iloc[col_idx]
            if pd.notna(raw):
                try:
                    timestamps.append(ts.tz_localize("UTC"))
                    values.append(float(raw))
                except Exception:
                    pass
        if timestamps:
            result[arc_key] = pd.Series(values, index=pd.DatetimeIndex(timestamps), name="count")

    return result


def _load_nam_weekly(path: Path) -> pd.DataFrame:
    """Load and normalize the NAM Weekly sheet from a BHI NA Excel file."""
    df = pd.read_excel(path, sheet_name="NAM Weekly", engine="openpyxl", header=10)
    df.columns = [str(c).strip() for c in df.columns]
    df["US_PublishDate"] = pd.to_datetime(df["US_PublishDate"], utc=True, errors="coerce")
    df["Rig Count Value"] = pd.to_numeric(df["Rig Count Value"], errors="coerce")
    df = df.dropna(subset=["US_PublishDate", "Rig Count Value", "Country"])
    df["Country"] = df["Country"].str.strip().str.upper()
    df["DrillFor"] = df["DrillFor"].str.strip()
    return df


def seed_na_weekly_archive(*paths: Path) -> None:
    """Seed BHI_US_TOTAL/OIL/GAS_RIGS and BHI_CANADA_RIGS from one or more NAM Weekly files.

    Accepts multiple files (e.g. the 2013-Aug 2025 archive and the Apr 2026 current file).
    Concatenates all, deduplicates by date (last file wins on overlap), then writes.
    """
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            log.warning("NAM Weekly file not found: %s — skipping", path.name)
            continue
        log.info("Loading NAM Weekly from %s", path.name)
        frames.append(_load_nam_weekly(path))

    if not frames:
        log.error("No NAM Weekly files found — aborting")
        return

    df = pd.concat(frames, ignore_index=True)
    # Deduplicate: keep last occurrence (later file wins on overlapping dates)
    df = df.drop_duplicates(
        subset=[
            "US_PublishDate",
            "Country",
            "DrillFor",
            "Location",
            "State/Province",
            "Trajectory",
        ],
        keep="last",
    )

    us = df[df["Country"] == "UNITED STATES"]
    ca = df[df["Country"] == "CANADA"]

    def _agg(sub: pd.DataFrame) -> pd.DataFrame:
        return (
            sub.groupby("US_PublishDate")["Rig Count Value"]
            .sum()
            .rename("count")
            .to_frame()
            .sort_index()
        )

    series_map = {
        "BHI_US_TOTAL_RIGS": _agg(us),
        "BHI_US_OIL_RIGS": _agg(us[us["DrillFor"] == "Oil"]),
        "BHI_US_GAS_RIGS": _agg(us[us["DrillFor"] == "Gas"]),
        "BHI_CANADA_RIGS": _agg(ca),
    }

    store = get_store()
    for arc_key, df_out in series_map.items():
        store.write_series("macro", arc_key, df_out)
        log.info(
            "Wrote %d rows to macro/%s  (%s → %s)",
            len(df_out),
            arc_key,
            df_out.index.min().date(),
            df_out.index.max().date(),
        )

    log.info("NA weekly archive seeding complete")


def seed_na_current_snapshot(path: Path) -> None:
    """Seed the current week's NA snapshot (single row per series) from a local file."""
    from data.collectors.baker_hughes import _parse_na_rig_count

    log.info("Seeding NA current snapshot from %s", path.name)
    excel_bytes = path.read_bytes()
    try:
        series_map = _parse_na_rig_count(excel_bytes)
    except Exception as e:
        log.error("Parse failed: %s", e)
        return
    store = get_store()
    for arc_key, df_new in series_map.items():
        store.write_series("macro", arc_key, df_new)
        log.info("Wrote %d row to macro/%s  date=%s", len(df_new), arc_key, df_new.index[0].date())
    log.info("NA snapshot seeding complete")


def seed_ww_us_canada_from_na() -> None:
    """Derive BHI_WW_US_RIGS and BHI_WW_CANADA_RIGS from existing weekly NA data.

    The WW Monthly archive only has regional aggregates (no US/Canada breakdown).
    The weekly NA series (BHI_US_TOTAL_RIGS, BHI_CANADA_RIGS) represent the same
    underlying counts — resample to monthly mean to produce the WW equivalents.
    """
    store = get_store()

    mapping = [
        ("BHI_US_TOTAL_RIGS", "BHI_WW_US_RIGS"),
        ("BHI_CANADA_RIGS", "BHI_WW_CANADA_RIGS"),
    ]

    for src_key, dst_key in mapping:
        try:
            weekly = store.read_series("macro", src_key)
        except Exception as e:
            log.error("Cannot read macro/%s: %s — skipping", src_key, e)
            continue

        if weekly.empty:
            log.warning("macro/%s is empty — skipping", src_key)
            continue

        # Ensure count column exists
        if "count" not in weekly.columns:
            log.error("macro/%s has no 'count' column — skipping", src_key)
            continue

        monthly = weekly["count"].resample("ME").mean().dropna().rename("count").to_frame()
        # Align index to month-start (consistent with WW archive)
        monthly.index = monthly.index.to_period("M").to_timestamp(how="start").tz_localize("UTC")

        store.write_series("macro", dst_key, monthly)
        log.info(
            "Wrote %d rows to macro/%s  (%s → %s)",
            len(monthly),
            dst_key,
            monthly.index.min().date(),
            monthly.index.max().date(),
        )

    log.info("BHI_WW_US_RIGS / BHI_WW_CANADA_RIGS seeding complete")


def seed_state_weekly(path: Path) -> None:
    log.info("Seeding US state weekly history from %s", path.name)
    xl = pd.ExcelFile(path, engine="openpyxl")
    sheets = xl.sheet_names
    log.info("Processing %d monthly sheets…", len(sheets))

    accumulator: dict[str, list[pd.Series]] = {}

    for i, sheet in enumerate(sheets):
        if i % 24 == 0:
            log.info("  Processing sheet %d/%d (%s)…", i + 1, len(sheets), sheet)
        try:
            parsed = _parse_state_sheet(xl, sheet)
            for arc_key, series in parsed.items():
                accumulator.setdefault(arc_key, []).append(series)
        except Exception as e:
            log.warning("Failed to parse sheet %s: %s", sheet, e)

    store = get_store()
    for arc_key, series_list in accumulator.items():
        combined = pd.concat(series_list).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        df = combined.to_frame(name="count")
        store.write_series("macro", arc_key, df)
        log.info("Wrote %d rows to macro/%s", len(df), arc_key)

    log.info("State weekly seeding complete")


# ---------------------------------------------------------------------------
# 5. State gap fill from NAM Weekly sheet (2024-present)
# ---------------------------------------------------------------------------


def seed_state_from_nam_weekly(*paths: Path) -> None:
    """Extend BHI state rig counts past Mar 2024 using NAM Weekly sheet.

    The NAM Weekly sheet in the current NA rig count Excel has State/Province
    breakdowns from 2024-01-05 onward. This function merges that data with
    the existing state series (seeded from the old Rigs by State archive).

    Existing data wins for overlapping timestamps.
    """
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            log.warning("NAM Weekly file not found: %s — skipping", path.name)
            continue
        log.info("Loading NAM Weekly from %s", path.name)
        df = _load_nam_weekly(path)
        df["State/Province"] = df["State/Province"].str.strip().str.upper()
        frames.append(df)

    if not frames:
        log.error("No NAM Weekly files provided — aborting state gap fill")
        return

    df = pd.concat(frames, ignore_index=True)

    store = get_store()

    for state_name, arc_key in NAM_WEEKLY_STATE_MAP.items():
        state_df = df[df["State/Province"] == state_name].copy()
        if state_df.empty:
            log.warning("No rows for state %r — skipping", state_name)
            continue

        new_data = (
            state_df.groupby("US_PublishDate")["Rig Count Value"]
            .sum()
            .rename("count")
            .to_frame()
            .sort_index()
        )

        # Merge with existing data: existing wins on overlap, new extends past end
        try:
            existing = store.read_series("macro", arc_key)
        except Exception:
            existing = pd.DataFrame()

        if existing.empty:
            store.write_series("macro", arc_key, new_data)
            log.info(
                "Wrote %d rows to macro/%s  (%s → %s)",
                len(new_data),
                arc_key,
                new_data.index.min().date(),
                new_data.index.max().date(),
            )
            continue

        existing_end = existing.index.max()
        new_rows = new_data[new_data.index > existing_end]

        if new_rows.empty:
            log.info("macro/%s already current — skip", arc_key)
            continue

        combined = pd.concat([existing, new_rows]).sort_index()
        combined = combined[~combined.index.duplicated(keep="first")]
        store.write_series("macro", arc_key, combined)
        log.info(
            "Extended macro/%s by %d rows → now ends %s",
            arc_key,
            len(new_rows),
            combined.index.max().date(),
        )

    log.info("State gap fill complete")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    na_archive = DOWNLOADS / "08-29-2025 North America Rig Count Report (1).xlsx"
    na_current = DOWNLOADS / "04-10-2026 North_America Rig_Count Report (2).xlsx"
    ww_archive = DOWNLOADS / "July-2025  WorldWide Rig Count Report.xlsx"
    state_file = DOWNLOADS / "Rigs by State_Jan 2000_Mar 2024.xlsx"

    seed_na_weekly_archive(na_archive, na_current)

    if na_current.exists():
        seed_na_current_snapshot(na_current)
    else:
        log.warning("NA current snapshot not found: %s", na_current)

    if ww_archive.exists():
        seed_ww_monthly(ww_archive)
    else:
        log.warning("WW archive not found: %s", ww_archive)

    seed_snapshots()

    # Derive WW US/Canada counts from weekly NA data (WW archive lacks country breakdown)
    seed_ww_us_canada_from_na()

    if state_file.exists():
        seed_state_weekly(state_file)
    else:
        log.warning("State file not found: %s", state_file)

    # Extend state series past Mar 2024 using current NA report
    seed_state_from_nam_weekly(na_current)

    log.info("All BHI historical seeding complete")
