"""
CFTC Commitments of Traders (COT) disaggregated collector.

Downloads weekly positioning data from CFTC bulk CSV files and writes per-symbol
net position series into the ``cot`` ArcticDB library via ``store.write_series()``.

Two CFTC report types are used:
  - Disaggregated (commodities): GC, MGC, CL
    URL template: https://www.cftc.gov/files/dea/history/fut_disagg_txt_{YYYY}.zip
    Commercial = Prod_Merc, Non-commercial = M_Money

  - Financial (equity index, FX, rates): ES, NQ, ZN, ZB, 6E
    URL template: https://www.cftc.gov/files/dea/history/fut_fin_txt_{YYYY}.zip
    Commercial = Dealer, Non-commercial = Lev_Money

Output columns per symbol: comm_net, noncomm_net, open_interest
ArcticDB key: ``{SYMBOL}_cot``  (e.g. ``ES_cot``)
Index: report date (Tuesday of report week, as YYYY-MM-DD in CFTC data)
"""

import io
import logging
import zipfile
from datetime import UTC, datetime
from typing import NamedTuple

import pandas as pd
import requests  # type: ignore[import-untyped]

from data.store import Store, get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CFTC symbol map
# ---------------------------------------------------------------------------

_DISAGG_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
_FIN_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"


class _SymbolSpec(NamedTuple):
    cftc_code: str  # CFTC_Contract_Market_Code value (stripped)
    report_type: str  # "disagg" or "fin"


# Symbol → (CFTC contract code, report type)
# Disaggregated: commercial = Prod_Merc, non-commercial = M_Money
# Financial:     commercial = Dealer,    non-commercial = Lev_Money
CFTC_SYMBOL_MAP: dict[str, _SymbolSpec] = {
    "GC": _SymbolSpec("088691", "disagg"),  # Gold - COMEX
    "MGC": _SymbolSpec("088695", "disagg"),  # Micro Gold - COMEX
    "CL": _SymbolSpec("067651", "disagg"),  # WTI Crude - NYMEX
    "ES": _SymbolSpec("13874+", "fin"),  # S&P 500 Consolidated - CME
    "NQ": _SymbolSpec("20974+", "fin"),  # NASDAQ-100 Consolidated - CME
    "ZN": _SymbolSpec("043602", "fin"),  # UST 10Y Note - CBOT
    "ZB": _SymbolSpec("020601", "fin"),  # UST Bond - CBOT
    "6E": _SymbolSpec("099741", "fin"),  # Euro FX - CME
}

# Columns to extract per report type
# Newer files (2017+) use YYYY-MM-DD; older files use MM_DD_YYYY format.
_DATE_COL_CANDIDATES = ["Report_Date_as_YYYY-MM-DD", "Report_Date_as_MM_DD_YYYY"]

_DISAGG_COLS = {
    "code": "CFTC_Contract_Market_Code",
    "oi": "Open_Interest_All",
    "comm_long": "Prod_Merc_Positions_Long_All",
    "comm_short": "Prod_Merc_Positions_Short_All",
    "noncomm_long": "M_Money_Positions_Long_All",
    "noncomm_short": "M_Money_Positions_Short_All",
}

_FIN_COLS = {
    "code": "CFTC_Contract_Market_Code",
    "oi": "Open_Interest_All",
    "comm_long": "Dealer_Positions_Long_All",
    "comm_short": "Dealer_Positions_Short_All",
    "noncomm_long": "Lev_Money_Positions_Long_All",
    "noncomm_short": "Lev_Money_Positions_Short_All",
}

_COL_MAP = {"disagg": _DISAGG_COLS, "fin": _FIN_COLS}

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def _url_for_year(year: int, report_type: str) -> str:
    if report_type == "disagg":
        return _DISAGG_URL.format(year=year)
    return _FIN_URL.format(year=year)


def _fetch_csv(url: str, timeout: int = 60) -> pd.DataFrame:
    """Download a CFTC zip and return the contained CSV as a DataFrame."""
    log.info("Fetching %s", url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        csv_names = [n for n in names if n.lower().endswith(".txt") or n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV/TXT file found in zip from {url}: {names}")
        with zf.open(csv_names[0]) as f:
            # Force CFTC_Contract_Market_Code as str to preserve leading zeros
            return pd.read_csv(f, low_memory=False, dtype={"CFTC_Contract_Market_Code": str})


def _years_to_fetch(backfill: bool = False) -> list[int]:
    """Return years to fetch.

    Args:
        backfill: If True, fetch full CFTC history from 2006 to current year.
                  If False (default), fetch the 3 most-recent years (incremental).
    """
    current = datetime.now(UTC).year
    if backfill:
        # Disaggregated report introduced Sept 2009; financial futures from 2006.
        # Use 2009 as safe start — both report types have data from then.
        return list(range(2009, current + 1))
    return [current - 2, current - 1, current]


# ---------------------------------------------------------------------------
# Parse / transform
# ---------------------------------------------------------------------------


def _parse_df(raw: pd.DataFrame, report_type: str) -> pd.DataFrame:
    """
    From a raw CFTC CSV DataFrame, extract date + comm_net + noncomm_net + open_interest.
    Returns a tidy DataFrame indexed by UTC DatetimeIndex.

    Handles two date column formats:
      - Newer (2017+): Report_Date_as_YYYY-MM-DD  (format: YYYY-MM-DD)
      - Older (pre-2017): Report_Date_as_MM_DD_YYYY  (format: MM/DD/YYYY)
    """
    cols = _COL_MAP[report_type]

    # Strip whitespace from column names
    raw.columns = raw.columns.str.strip()

    # Detect date column
    date_col = next((c for c in _DATE_COL_CANDIDATES if c in raw.columns), None)
    if date_col is None:
        raise ValueError(
            f"Cannot find date column. Tried: {_DATE_COL_CANDIDATES}. "
            f"Available: {list(raw.columns[:10])}"
        )

    needed = [
        date_col,
        cols["code"],
        cols["oi"],
        cols["comm_long"],
        cols["comm_short"],
        cols["noncomm_long"],
        cols["noncomm_short"],
    ]

    sub = raw[needed].copy()
    sub.columns = [
        "date",
        "code",
        "open_interest",
        "comm_long",
        "comm_short",
        "noncomm_long",
        "noncomm_short",
    ]

    # Strip whitespace from code column
    sub["code"] = sub["code"].astype(str).str.strip()

    # Parse date — handle both YYYY-MM-DD and MM/DD/YYYY
    sub["date"] = pd.to_datetime(sub["date"], utc=False)
    sub["date"] = sub["date"].dt.tz_localize("UTC")

    # Convert position columns to numeric
    for col in ["open_interest", "comm_long", "comm_short", "noncomm_long", "noncomm_short"]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce")

    sub["comm_net"] = sub["comm_long"] - sub["comm_short"]
    sub["noncomm_net"] = sub["noncomm_long"] - sub["noncomm_short"]

    return sub[["date", "code", "comm_net", "noncomm_net", "open_interest"]]


# ---------------------------------------------------------------------------
# Public collect function
# ---------------------------------------------------------------------------


def collect(symbols: list[str] | None = None, backfill: bool = False) -> None:
    """
    Download CFTC COT data and write to ArcticDB ``cot`` library.

    Args:
        symbols: list of symbol strings from CFTC_SYMBOL_MAP keys.
                 Defaults to all symbols in CFTC_SYMBOL_MAP.
        backfill: If True, fetch full history from 2006 to present (~20yr).
                  If False (default), fetch the 3 most-recent years.
    """
    if symbols is None:
        symbols = list(CFTC_SYMBOL_MAP.keys())

    unknown = [s for s in symbols if s not in CFTC_SYMBOL_MAP]
    if unknown:
        raise ValueError(f"Unknown COT symbols: {unknown}. Known: {list(CFTC_SYMBOL_MAP.keys())}")

    store = get_store()
    years = _years_to_fetch(backfill=backfill)
    if backfill:
        log.info("Backfill mode: fetching %d years (%d → %d)", len(years), years[0], years[-1])

    # Group symbols by report type to minimise downloads
    disagg_syms = [s for s in symbols if CFTC_SYMBOL_MAP[s].report_type == "disagg"]
    fin_syms = [s for s in symbols if CFTC_SYMBOL_MAP[s].report_type == "fin"]

    # --- collect disaggregated ---
    if disagg_syms:
        _collect_report(store, disagg_syms, "disagg", years)

    # --- collect financial ---
    if fin_syms:
        _collect_report(store, fin_syms, "fin", years)

    log.info("COT collection complete for %s", symbols)


def _collect_report(
    store: Store,
    symbols: list[str],
    report_type: str,
    years: list[int],
) -> None:
    """Download annual files for *report_type* and write each symbol's series."""
    # Build combined parsed dataframe across all years
    frames: list[pd.DataFrame] = []
    for year in years:
        url = _url_for_year(year, report_type)
        try:
            raw = _fetch_csv(url)
            parsed = _parse_df(raw, report_type)
            frames.append(parsed)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                log.warning(
                    "COT file not yet available for year %d (%s): %s", year, report_type, url
                )
            else:
                raise

    if not frames:
        log.warning("No COT data fetched for report_type=%s years=%s", report_type, years)
        return

    combined = pd.concat(frames, ignore_index=True)

    for sym in symbols:
        spec = CFTC_SYMBOL_MAP[sym]
        mask = combined["code"] == spec.cftc_code
        sym_df = combined.loc[mask, ["date", "comm_net", "noncomm_net", "open_interest"]].copy()
        sym_df = sym_df.set_index("date")
        sym_df = sym_df.sort_index()
        sym_df = sym_df[~sym_df.index.duplicated(keep="last")]

        if sym_df.empty:
            log.warning("No COT rows found for %s (code=%s)", sym, spec.cftc_code)
            continue

        arc_key = f"{sym}_cot"
        store.write_series("cot", arc_key, sym_df)
        log.info("Wrote %d rows to cot/%s", len(sym_df), arc_key)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="CFTC COT collector")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Fetch full history from 2006 to present (~20yr, ~40 downloads)",
    )
    parser.add_argument(
        "--symbols", nargs="+", default=None,
        help="Symbols to collect (default: all)",
    )
    args = parser.parse_args()
    collect(symbols=args.symbols, backfill=args.backfill)
