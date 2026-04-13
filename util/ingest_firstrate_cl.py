"""
CL 1H historical data extension — FirstRate CSV or IBKR reseed.

Extends CL_continuous_1H in the ArcticDB futures library.

Usage:
    # Path A — IBKR reseed (IB Gateway required on port 4002):
    python3 util/ingest_firstrate_cl.py --ibkr

    # Path B — FirstRate Data CSV ingest (purchased CSV):
    python3 util/ingest_firstrate_cl.py --csv /path/to/firstrate_CL_1H.csv

FirstRate CSV format (expected):
    datetime,open,high,low,close,volume
    2020-01-02 09:00:00,63.15,63.28,62.90,63.10,12345
    ...
    - datetime column in UTC or local exchange time (auto-detected by UTC flag)
    - OHLCV columns (case-insensitive)

IBKR reseed:
    Uses _seed_stitched to fetch all available contracts (up to max_contract_age_days=1825).
    Writes result directly to 'CL_continuous_1H' store key (not the default 'CL_1H' key).
    Deduplicates and merges with any existing data (no duplicate timestamps).
    New bars are prepended; existing bars from current start onwards are preserved.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from data.config import get_settings
from data.store import Store, get_store

STORE_LIB = "futures"
STORE_KEY = "CL_continuous_1H"


def _ingest_ibkr() -> int:
    """Reseed CL 1H via IBKR. Writes to CL_continuous_1H store key."""
    try:
        from ib_insync import IB

        from data.collectors.ibkr_futures import _TIMEFRAMES, _get_contract_chain, _ratio_stitch
        from data.collectors.ibkr_futures import _fetch_contract_bars
    except ImportError as exc:
        print(f"ERROR: ib_insync not available — {exc}", file=sys.stderr)
        return 1

    s = get_settings()
    store = get_store()
    tf = _TIMEFRAMES["1H"]

    print(f"Connecting to IB Gateway at {s.ibkr_host}:{s.ibkr_port}...")
    ib = IB()  # type: ignore[no-untyped-call]
    try:
        ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id)

        print("Fetching CL contract chain (max_contract_age_days=1825)...")
        chain = _get_contract_chain(
            ib, "CL", years_back=3, max_age_days=tf["max_contract_age_days"]
        )
        print(f"  {len(chain)} contracts")

        frames: list[pd.DataFrame] = []
        for i, contract in enumerate(chain, 1):
            expiry = contract.lastTradeDateOrContractMonth[:8]
            print(f"  [{i}/{len(chain)}] CL exp={expiry}", flush=True)
            df = _fetch_contract_bars(ib, contract, tf, f"CL 1H exp={expiry}")
            if not df.empty:
                date_range = f"{df.index.min().date()} → {df.index.max().date()}"
                print(f"    {len(df)} bars  ({date_range})", flush=True)
                frames.append(df)
            else:
                print("    no bars", flush=True)

    finally:
        ib.disconnect()  # type: ignore[no-untyped-call]

    if not frames:
        print("ERROR: no bars returned from IBKR", file=sys.stderr)
        return 1

    print(f"Stitching {len(frames)} contracts...")
    new_df = _ratio_stitch(frames, label="CL 1H")

    return _merge_and_write(store, new_df, source="IBKR")


def _ingest_csv(csv_path: Path, utc: bool = False) -> int:
    """Ingest FirstRate Data CSV. Writes to CL_continuous_1H store key."""
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    print(f"Reading {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        print(f"ERROR: failed to read CSV — {exc}", file=sys.stderr)
        return 1

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # Detect datetime column
    dt_col = next(
        (c for c in df.columns if c in ("datetime", "date", "timestamp", "time")), None
    )
    if dt_col is None:
        print(f"ERROR: no datetime column found. Columns: {list(df.columns)}", file=sys.stderr)
        return 1

    # Parse and localize datetime
    df[dt_col] = pd.to_datetime(df[dt_col])
    if utc:
        df[dt_col] = df[dt_col].dt.tz_localize("UTC")
    else:
        # Assume US/Eastern (CL pit hours) — convert to UTC
        df[dt_col] = df[dt_col].dt.tz_localize("America/New_York", ambiguous="infer").dt.tz_convert("UTC")

    df = df.set_index(dt_col).sort_index()

    # Validate OHLCV columns
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        print(f"ERROR: missing columns: {missing}. Found: {list(df.columns)}", file=sys.stderr)
        return 1

    df = df[["open", "high", "low", "close", "volume"]].copy()
    df = df.astype(float)
    df["volume"] = df["volume"].astype(int)

    print(f"  {len(df)} bars  ({df.index.min().date()} → {df.index.max().date()})")

    store = get_store()
    return _merge_and_write(store, df, source="FirstRate CSV")


def _merge_and_write(store: Store, new_df: pd.DataFrame, source: str) -> int:
    """Merge new_df with existing CL_continuous_1H. No duplicate timestamps."""
    existing_start: str | None = None
    existing_end: str | None = None

    if store.has_symbol(STORE_LIB, STORE_KEY):
        existing = store.read_bars(STORE_LIB, STORE_KEY)
        existing_start = str(existing.index.min().date())
        existing_end = str(existing.index.max().date())
        print(
            f"Existing {STORE_KEY}: {len(existing)} bars "
            f"({existing_start} → {existing_end})"
        )
        # Merge — drop duplicates, keep new data for overlapping timestamps
        combined = pd.concat([new_df, existing])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()
    else:
        print(f"No existing {STORE_KEY} — writing fresh")
        combined = new_df.sort_index()

    print(
        f"Writing {len(combined)} bars to {STORE_KEY} "
        f"({combined.index.min().date()} → {combined.index.max().date()})..."
    )
    # CL_continuous_1H is a legacy store key that predates the _FUTURES_KEY_RE validation.
    # Write directly to the ArcticDB lib to preserve the key used by the liquidity_sweep_adapter.
    lib = store._libs[STORE_LIB]
    if lib.has_symbol(STORE_KEY):
        lib.delete(STORE_KEY)
    lib.write(STORE_KEY, combined)

    new_start = str(combined.index.min().date())
    new_end = str(combined.index.max().date())
    print(f"Done.")
    print(f"  Source: {source}")
    print(f"  Old range: {existing_start} → {existing_end}")
    print(f"  New range: {new_start} → {new_end}")

    # Verify no duplicate timestamps
    dupes = combined.index.duplicated().sum()
    if dupes > 0:
        print(f"WARNING: {dupes} duplicate timestamps detected after merge", file=sys.stderr)
        return 1

    print(f"  Duplicate check: PASS (0 duplicate timestamps)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extend CL 1H history in ArcticDB via IBKR reseed or FirstRate CSV."
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--ibkr", action="store_true", help="Reseed from IBKR (IB Gateway required)")
    group.add_argument("--csv", type=Path, help="Path to FirstRate Data CSV file")
    ap.add_argument(
        "--utc",
        action="store_true",
        default=False,
        help="CSV datetimes are already in UTC (skip US/Eastern conversion)",
    )
    args = ap.parse_args()

    if args.ibkr:
        sys.exit(_ingest_ibkr())
    else:
        sys.exit(_ingest_csv(args.csv, utc=args.utc))


if __name__ == "__main__":
    main()
