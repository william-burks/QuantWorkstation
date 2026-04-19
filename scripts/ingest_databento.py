"""
Ingest Databento GLBX.MDP3 OHLCV-1m DBN file into ArcticDB futures library.

Reads a downloaded DBN (.dbn.zst) file, splits by root symbol, stitches
individual contract bars into a continuous front-month series, resamples into
all 11 IBKR-compatible timeframes, deduplicates against existing data, and
writes to ArcticDB using the same key convention as ibkr_futures.py.

Symbol handling:
  Databento returns individual contract codes (ESH2, CLF2, GCZ5) when the
  download used stype_out="instrument_id". This script parses the root ticker
  from each contract code, discards spreads (contain '-') and user-defined
  instruments (start with 'UD:'), then builds a continuous front-month series
  by selecting the nearest-expiry contract at each timestamp.

Schema alignment:
  IBKR data written by ibkr_futures.py has:
    index.name="timestamp", volume=float64, market="futures", source="ibkr", adjusted=False
  Databento data is normalized to the same schema before writing.

Merge strategy:
  - Existing IBKR data takes priority for overlapping timestamps.
  - Databento fills historical gaps (before IBKR data starts).
  - New Databento rows (after existing end) are appended normally.

Key convention (matches ibkr_futures.py):
  Intraday (5min–8H): {SYMBOL}_{tf}          e.g. ES_5min, ES_1H
  Daily/Weekly/Monthly: {SYMBOL}_contfut_{tf} e.g. ES_contfut_1D

Usage:
    python scripts/ingest_databento.py ~/Downloads/GLBX-20260415-9Q6UT9P7VC/glbx-mdp3-*.dbn.zst
"""

import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import databento as db
import pandas as pd

from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeframe resample config — mirrors ibkr_futures._TIMEFRAMES
# ---------------------------------------------------------------------------

# (arc_key_suffix, pandas_resample_rule, is_contfut)
TIMEFRAMES: list[tuple[str, str, bool]] = [
    ("5min", "5min", False),
    ("10min", "10min", False),
    ("15min", "15min", False),
    ("30min", "30min", False),
    ("1H", "1h", False),
    ("2H", "2h", False),
    ("4H", "4h", False),
    ("8H", "8h", False),
    ("1D", "1D", True),
    ("1W", "1W", True),
    ("1M", "1ME", True),
]

# Databento parent symbol → ArcticDB root symbol
SYMBOL_MAP: dict[str, str] = {
    "ES": "ES",
    "CL": "CL",
    "GC": "GC",
    "ZN": "ZN",
    "NQ": "NQ",
    "RTY": "RTY",
    "6E": "6E",
    "NG": "NG",
    "ZB": "ZB",
    "SI": "SI",
    "HG": "HG",
    "6J": "6J",
    "6B": "6B",
}

# ---------------------------------------------------------------------------
# Contract code parsing
# ---------------------------------------------------------------------------

# CME month codes: F=Jan G=Feb H=Mar J=Apr K=May M=Jun N=Jul Q=Aug U=Sep V=Oct X=Nov Z=Dec
_MONTH_CODES: dict[str, int] = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}

# Matches e.g. ESH2, CLF25, GCZ5, ZNM4 — root + month_letter + 1-2 digit year
_CONTRACT_RE = re.compile(r"^([A-Z0-9]+)([FGHJKMNQUVXZ])(\d{1,2})$")


def _parse_contract(symbol: str) -> tuple[str, pd.Timestamp] | None:
    """Return (root, approx_expiry) for an outright futures contract code.

    Returns None for spreads (contain '-'), user-defined instruments ('UD:'),
    or symbols that don't match the contract code pattern.
    """
    if "-" in symbol or symbol.startswith("UD:"):
        return None
    m = _CONTRACT_RE.match(symbol)
    if not m:
        return None
    root, month_code, year_str = m.groups()
    month = _MONTH_CODES[month_code]
    yr = int(year_str)
    # 1-digit year: 2020s decade (data spans 2021–2026)
    # 2-digit year: 00–49 → 2000–2049
    year = (2020 + yr) if len(year_str) == 1 else (2000 + yr if yr < 50 else 1900 + yr)
    expiry = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    return root, expiry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arc_key(symbol: str, tf_key: str, contfut: bool) -> str:
    if contfut:
        return f"{symbol}_contfut_{tf_key}"
    return f"{symbol}_{tf_key}"


def _resample(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1min OHLCV DataFrame to a coarser timeframe."""
    agg = df_1m.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    agg = agg.dropna(subset=["open", "close"])
    agg = agg[agg["volume"] > 0]
    return agg


def _normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Databento resampled bars to match the ibkr_futures.py schema.

    ibkr_futures.py writes:
      index.name="timestamp", volume=float64, market="futures", source="ibkr", adjusted=False
    """
    df = df.copy()
    df.index.name = "timestamp"
    df["volume"] = df["volume"].astype(float)
    df["market"] = "futures"
    df["source"] = "databento"
    df["adjusted"] = False
    return df


def _write_with_merge(df_new: pd.DataFrame, store: Any, arc_key: str) -> tuple[int, str]:
    """Write Databento bars to ArcticDB, merging with any existing IBKR data.

    Strategy:
    - Existing data takes priority for overlapping timestamps.
    - Databento rows BEFORE existing data start → prepend (requires full rewrite).
    - Databento rows AFTER existing data end → normal append.

    Returns (rows_written, action) for logging.
    """
    try:
        existing = store.read_bars("futures", arc_key)
    except Exception:
        existing = pd.DataFrame()

    if existing.empty:
        store.overwrite_bars("futures", arc_key, df_new)
        return len(df_new), "write (no prior data)"

    existing_start = existing.index.min()
    existing_end = existing.index.max()

    historical = df_new[df_new.index < existing_start]
    new_after = df_new[df_new.index > existing_end]

    if historical.empty and new_after.empty:
        return 0, "skip (fully covered)"

    if not historical.empty:
        # Must rewrite: merge Databento historical + existing + any new trailing rows
        parts = [historical]
        parts.append(existing)
        if not new_after.empty:
            # Align new_after schema to existing before concat
            for col in existing.columns:
                if col not in new_after.columns:
                    new_after = new_after.copy()
                    new_after[col] = existing[col].iloc[0]
            parts.append(new_after)

        merged = pd.concat(parts)
        # Existing wins for overlapping timestamps (put it last, keep='last')
        # historical + existing → existing takes priority on any overlap
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()

        store.overwrite_bars("futures", arc_key, merged)
        action = f"rewrite (prepended {len(historical)} historical rows"
        if not new_after.empty:
            action += f" + appended {len(new_after)} new rows"
        action += ")"
        return len(historical) + len(new_after), action
    else:
        # Only new trailing rows — align schema and append
        for col in existing.columns:
            if col not in new_after.columns:
                new_after = new_after.copy()
                new_after[col] = existing[col].iloc[0]
        store.write_bars("futures", arc_key, new_after)
        return len(new_after), f"append ({len(new_after)} new rows)"


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------


def ingest(dbn_path: Path) -> None:
    log.info("Loading DBN file: %s", dbn_path)
    store_obj = db.DBNStore.from_file(str(dbn_path))

    # to_df() with map_symbols=True returns individual contract codes when
    # stype_out="instrument_id" was used at download time (ESH2, CLF2, etc.)
    df_all = store_obj.to_df(schema=db.Schema.OHLCV_1M, map_symbols=True)

    if df_all.empty:
        log.error("DBN file returned empty DataFrame — check schema/file")
        return

    log.info("Loaded %d total 1min rows across all symbols", len(df_all))

    # Normalize index to UTC DatetimeIndex
    if not isinstance(df_all.index, pd.DatetimeIndex):
        df_all.index = pd.to_datetime(df_all.index, utc=True)
    elif df_all.index.tz is None:
        df_all.index = df_all.index.tz_localize("UTC")
    else:
        df_all.index = df_all.index.tz_convert("UTC")

    df_all = df_all.sort_index()

    # Normalize price columns (Databento stores prices as int × 1e-9)
    for col in ["open", "high", "low", "close"]:
        if col in df_all.columns and df_all[col].dtype == "int64":
            df_all[col] = df_all[col] / 1e9

    symbols_found = df_all["symbol"].unique() if "symbol" in df_all.columns else []
    log.info("Raw symbols in file: %d unique (individual contract codes)", len(symbols_found))

    # Parse each contract code → (root, expiry), skip spreads and unknowns
    root_contracts: dict[str, list[tuple[str, pd.Timestamp]]] = defaultdict(list)
    skipped = 0
    for sym in symbols_found:
        parsed = _parse_contract(sym)
        if parsed is None:
            skipped += 1
            continue
        root, expiry = parsed
        if root not in SYMBOL_MAP:
            skipped += 1
            continue
        root_contracts[root].append((sym, expiry))

    log.info(
        "Mapped roots: %s  |  skipped %d symbols (spreads / unmapped)",
        sorted(root_contracts.keys()),
        skipped,
    )

    arc_store = get_store()

    for raw_root in sorted(root_contracts.keys()):
        arc_sym = SYMBOL_MAP[raw_root]
        contracts = root_contracts[raw_root]
        contracts.sort(key=lambda x: x[1])  # sort by expiry ascending

        # Build continuous front-month series:
        # Concatenate all contracts, sort by expiry so front month comes first,
        # then keep only the first (front-month) row for each timestamp.
        pieces = []
        for sym, expiry in contracts:
            mask = df_all["symbol"] == sym
            piece = df_all.loc[mask, ["open", "high", "low", "close", "volume"]].copy()
            piece["_expiry"] = expiry
            pieces.append(piece)

        if not pieces:
            continue

        df_combined = pd.concat(pieces)
        # Sort by expiry first so front-month rows come first for each timestamp
        df_combined = df_combined.sort_values("_expiry")
        # For duplicate timestamps, keep front-month (first after expiry sort)
        df_sym = df_combined[~df_combined.index.duplicated(keep="first")]
        df_sym = df_sym.drop(columns=["_expiry"]).sort_index()

        log.info(
            "[%s] %d 1min rows from %d contracts  (%s → %s)",
            arc_sym,
            len(df_sym),
            len(contracts),
            df_sym.index.min().date(),
            df_sym.index.max().date(),
        )

        for tf_key, resample_rule, contfut in TIMEFRAMES:
            df_tf = _resample(df_sym, resample_rule)
            if df_tf.empty:
                log.info("  [%s %s] empty after resample — skipping", arc_sym, tf_key)
                continue

            df_tf = _normalize_schema(df_tf)

            key = _arc_key(arc_sym, tf_key, contfut)
            rows, action = _write_with_merge(df_tf, arc_store, key)

            if rows == 0:
                log.info("  [%s %s] %s", arc_sym, tf_key, action)
            else:
                log.info("  [%s %s] %d rows — %s", arc_sym, tf_key, rows, action)

    log.info("Databento ingestion complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        # Auto-detect from default download location
        default = Path.home() / "Downloads" / "GLBX-20260415-9Q6UT9P7VC"
        candidates = list(default.glob("*.dbn.zst"))
        if not candidates:
            print("Usage: python scripts/ingest_databento.py <path/to/file.dbn.zst>")
            sys.exit(1)
        dbn_path = candidates[0]
    else:
        dbn_path = Path(sys.argv[1])

    if not dbn_path.exists():
        print(f"File not found: {dbn_path}")
        sys.exit(1)

    ingest(dbn_path)
