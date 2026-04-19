"""
Ingest historical Coinbase OHLCV data into ArcticDB crypto library.

Fetches 1-minute bars from the Coinbase Advanced Trade public API (no auth
required) back to START_DATE, resamples into all 11 standard timeframes, and
merges with any existing Alpaca data (Alpaca wins for overlapping timestamps).

Timeframe key convention (matches futures library):
  1min, 5min, 10min, 15min, 30min, 1H, 2H, 4H, 8H, 1D, 1W, 1M

Alpaca key migration:
  Existing Alpaca keys (BTC/USD_5T, BTC/USD_15T, etc.) are merged in during
  the write step. Old Alpaca keys are left in place — remove manually once
  research code is updated to the new naming.

Runtime estimate (7yr, 2 symbols):
  ~24,500 requests at 0.12s sleep ≈ 1.5–2 hours

Usage:
    python util/ingest_coinbase_crypto.py
    python util/ingest_coinbase_crypto.py --symbols BTC-USD ETH-USD --start 2019-01-01
"""

import argparse
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.store import get_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_START = datetime(2019, 1, 1, tzinfo=UTC)
DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD"]

API_BASE = "https://api.coinbase.com/api/v3/brokerage/market/products"
GRANULARITY = "ONE_MINUTE"
BARS_PER_REQUEST = 300  # Coinbase hard cap
REQUEST_SLEEP = 0.12  # ~8 req/sec — safely under 10/sec public limit

# (arc_key_suffix, pandas_resample_rule, closed/label="left" for intraday)
TIMEFRAMES: list[tuple[str, str]] = [
    ("5min", "5min"),
    ("10min", "10min"),
    ("15min", "15min"),
    ("30min", "30min"),
    ("1H", "1h"),
    ("2H", "2h"),
    ("4H", "4h"),
    ("8H", "8h"),
    ("1D", "1D"),
    ("1W", "1W"),
    ("1M", "1ME"),
]

# Alpaca suffix → new suffix, for migrating existing data into merged series
ALPACA_KEY_MAP: dict[str, str] = {
    "5T": "5min",
    "15T": "15min",
    "1H": "1H",
    "4H": "4H",
    "1D": "1D",
    "1W": "1W",
}


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------


def _arc_symbol(coinbase_id: str) -> str:
    """BTC-USD → BTC/USD"""
    return coinbase_id.replace("-", "/")


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------


def _fetch_chunk(
    product_id: str,
    start_ts: int,
    end_ts: int,
    session: requests.Session,
) -> list[dict[str, Any]]:
    """Fetch up to BARS_PER_REQUEST 1-min candles. Retries on 429 / transient errors."""
    url = f"{API_BASE}/{product_id}/candles"
    params = {"granularity": GRANULARITY, "start": str(start_ts), "end": str(end_ts)}

    for attempt in range(6):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = 2**attempt
                log.warning("Rate limited — sleeping %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            candles: list[dict[str, Any]] = resp.json().get("candles", [])
            return candles
        except requests.RequestException as exc:
            if attempt == 5:
                raise
            wait = 2**attempt
            log.warning("Request error (attempt %d): %s — retrying in %ds", attempt + 1, exc, wait)
            time.sleep(wait)

    return []


def fetch_1min(product_id: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Pull all 1-min bars for *product_id* from *start* to *end*.

    Paginates in BARS_PER_REQUEST-minute chunks. Returns a UTC DatetimeIndex
    DataFrame with columns open/high/low/close/volume (float64), sorted and
    deduplicated.
    """
    session = requests.Session()
    session.headers["User-Agent"] = "QuantWorkstation/1.0"

    chunk_delta = timedelta(minutes=BARS_PER_REQUEST)
    total_minutes = int((end - start).total_seconds() / 60)
    total_chunks = (total_minutes // BARS_PER_REQUEST) + 1

    all_candles: list[dict[str, Any]] = []
    current = start
    chunk_num = 0

    log.info(
        "[%s] Fetching %d min of 1-min bars (%d chunks)…", product_id, total_minutes, total_chunks
    )

    while current < end:
        chunk_end = min(current + chunk_delta, end)
        candles = _fetch_chunk(
            product_id,
            int(current.timestamp()),
            int(chunk_end.timestamp()),
            session,
        )
        all_candles.extend(candles)
        chunk_num += 1

        if chunk_num % 1000 == 0:
            pct = 100.0 * chunk_num / total_chunks
            log.info(
                "[%s]  %d/%d chunks (%.0f%%) — %d bars so far",
                product_id,
                chunk_num,
                total_chunks,
                pct,
                len(all_candles),
            )

        current = chunk_end
        time.sleep(REQUEST_SLEEP)

    if not all_candles:
        log.warning("[%s] No candles returned", product_id)
        return pd.DataFrame()

    df = pd.DataFrame(all_candles)
    df["start"] = pd.to_datetime(df["start"].astype(int), unit="s", utc=True)
    df = (
        df.rename(columns={"start": "timestamp"})
        .set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        .astype(float)
        .sort_index()
    )
    df = df[~df.index.duplicated(keep="last")]

    log.info(
        "[%s] Fetched %d 1-min bars  (%s → %s)",
        product_id,
        len(df),
        df.index.min().date(),
        df.index.max().date(),
    )
    return df


# ---------------------------------------------------------------------------
# Resample + schema
# ---------------------------------------------------------------------------


def _resample(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = df_1m.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    agg = agg.dropna(subset=["open", "close"])
    return agg[agg["volume"] > 0]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index.name = "timestamp"
    df["volume"] = df["volume"].astype(float)
    df["market"] = "crypto"
    df["source"] = "coinbase"
    df["adjusted"] = False
    return df


# ---------------------------------------------------------------------------
# Write with merge
# ---------------------------------------------------------------------------


def _load_existing(store: Any, arc_sym: str, new_suffix: str, alpaca_suffix: str | None) -> pd.DataFrame:
    """Read existing data from new key; fall back to old Alpaca key if not found."""
    arc_key = f"{arc_sym}_{new_suffix}"
    try:
        df = store.read_bars("crypto", arc_key)
        if not df.empty:
            return df
    except Exception:
        pass

    if alpaca_suffix:
        old_key = f"{arc_sym}_{alpaca_suffix}"
        try:
            df = store.read_bars("crypto", old_key)
            if not df.empty:
                log.info("  Migrating Alpaca data from crypto/%s into crypto/%s", old_key, arc_key)
                return df
        except Exception:
            pass

    return pd.DataFrame()


def _write_merged(
    df_coinbase: pd.DataFrame,
    store: Any,
    arc_sym: str,
    new_suffix: str,
    alpaca_suffix: str | None,
) -> None:
    """Write Coinbase bars merged with any existing Alpaca data.

    Existing data (Alpaca) wins for overlapping timestamps.
    Coinbase fills the historical period before existing data starts.
    """
    arc_key = f"{arc_sym}_{new_suffix}"
    existing = _load_existing(store, arc_sym, new_suffix, alpaca_suffix)

    if existing.empty:
        store.overwrite_bars("crypto", arc_key, _normalize(df_coinbase))
        log.info("  [%s] %d rows — write", arc_key, len(df_coinbase))
        return

    existing_start = existing.index.min()
    existing_end = existing.index.max()

    historical = df_coinbase[df_coinbase.index < existing_start]
    new_after = df_coinbase[df_coinbase.index > existing_end]

    if historical.empty and new_after.empty:
        log.info("  [%s] fully covered — skip", arc_key)
        return

    if not historical.empty:
        hist_norm = _normalize(historical)
        parts = [hist_norm, existing]
        if not new_after.empty:
            new_norm = _normalize(new_after)
            for col in existing.columns:
                if col not in new_norm.columns:
                    new_norm[col] = existing[col].iloc[0]
            parts.append(new_norm)
        merged = pd.concat(parts)
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        store.overwrite_bars("crypto", arc_key, merged)
        log.info(
            "  [%s] %d rows — rewrite (prepended %d historical rows)",
            arc_key,
            len(merged),
            len(historical),
        )
    else:
        new_norm = _normalize(new_after)
        for col in existing.columns:
            if col not in new_norm.columns:
                new_norm[col] = existing[col].iloc[0]
        store.write_bars("crypto", arc_key, new_norm)
        log.info("  [%s] %d rows — append", arc_key, len(new_after))


# ---------------------------------------------------------------------------
# Main ingest
# ---------------------------------------------------------------------------


def ingest(product_id: str, start: datetime, end: datetime) -> None:
    """Full pipeline for one symbol: fetch → resample → merge → write."""
    arc_sym = _arc_symbol(product_id)
    log.info("=== Ingesting %s (%s) ===", product_id, arc_sym)

    df_1m = fetch_1min(product_id, start, end)
    if df_1m.empty:
        log.error("[%s] No data fetched — aborting", product_id)
        return

    # Store 1-min base under new key (merge with existing BTC/USD_1T if present)
    store = get_store()
    _write_merged(df_1m, store, arc_sym, "1min", "1T")

    # Resample to all 11 timeframes
    reverse_alpaca = {v: k for k, v in ALPACA_KEY_MAP.items()}
    for tf_suffix, rule in TIMEFRAMES:
        df_tf = _resample(df_1m, rule)
        if df_tf.empty:
            log.warning("  [%s_%s] empty after resample — skipping", arc_sym, tf_suffix)
            continue
        alpaca_suffix = reverse_alpaca.get(tf_suffix)
        _write_merged(df_tf, store, arc_sym, tf_suffix, alpaca_suffix)

    log.info("=== %s complete ===", product_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Ingest Coinbase historical crypto OHLCV")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help="Coinbase product IDs (default: BTC-USD ETH-USD)",
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START.strftime("%Y-%m-%d"),
        help="Start date YYYY-MM-DD (default: 2019-01-01)",
    )
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=UTC)
    end_dt = datetime.now(tz=UTC)

    total_minutes = int((end_dt - start_dt).total_seconds() / 60)
    total_requests = (total_minutes // BARS_PER_REQUEST + 1) * len(args.symbols)
    est_seconds = total_requests * REQUEST_SLEEP
    log.info(
        "Estimated runtime: %.0f requests × %.2fs = %.0f min",
        total_requests,
        REQUEST_SLEEP,
        est_seconds / 60,
    )

    for sym in args.symbols:
        ingest(sym, start_dt, end_dt)

    log.info("All done.")
