"""
IBKR futures OHLCV batch collector via ib_insync.

Requires IB Gateway or TWS running locally on the configured port.

Two collection modes:
  CONTFUT (daily/weekly):
    Single request with empty endDateTime. IBKR stitches and back-adjusts
    automatically. Supports "3 Y" duration in one shot.

  Stitched FUT (intraday — 1min, 5min, 15min, 1H, 4H):
    Fetches each individual expired contract separately using multi-chunk
    backward requests (regular FUT supports endDateTime). Applies ratio
    back-adjustment at roll dates to produce a continuous series.

IMPORTANT — Price adjustment:
    All stored data uses ratio back-adjustment at roll dates. Historical prices
    are scaled so there are no gaps at rollovers, preserving percentage returns.

    Suitable for:  return-based backtesting, technical indicators (RSI, EMA, ATR)
    NOT suitable for: dollar P&L anchored to historical prices, spread analysis,
                      or any use case requiring historically accurate price levels

Store key format: "{root}_continuous_{timeframe}"  e.g. "MES_continuous_1H"
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from ib_insync import IB, Contract

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# contfut=True: single CONTFUT request, no endDateTime stepping.
# contfut=False: stitch individual expired FUT contracts.
# contract_chunks: max requests per contract when stitching (covers ~3 months each).
_TIMEFRAMES: dict[str, dict] = {
    # max_contract_age_days: skip contracts older than this (IBKR data retention limit)
    # "1min":  {"bar_size": "1 min",   "duration": "1 D",  "chunk_days": 1,  "contract_chunks": 70, "max_contract_age_days": 180,  "use_rth": False, "contfut": False},
    "5min":  {"bar_size": "5 mins",  "duration": "1 W",  "chunk_days": 7,  "contract_chunks": 14, "max_contract_age_days": 365,  "use_rth": False, "contfut": False},
    "15min": {"bar_size": "15 mins", "duration": "2 W",  "chunk_days": 14, "contract_chunks": 7,  "max_contract_age_days": 730,  "use_rth": False, "contfut": False},
    "1H":    {"bar_size": "1 hour",  "duration": "1 M",  "chunk_days": 30, "contract_chunks": 4,  "max_contract_age_days": 1095, "use_rth": False, "contfut": False},
    "4H":    {"bar_size": "4 hours", "duration": "1 M",  "chunk_days": 30, "contract_chunks": 4,  "max_contract_age_days": 1095, "use_rth": False, "contfut": False},
    # "1D":    {"bar_size": "1 day",   "duration": "3 Y",  "chunk_days": None, "contract_chunks": None, "max_contract_age_days": None, "use_rth": True, "contfut": True},
    # "1W":    {"bar_size": "1 week",  "duration": "3 Y",  "chunk_days": None, "contract_chunks": None, "max_contract_age_days": None, "use_rth": True, "contfut": True},
}

_CONTRACT_SPECS: dict[str, dict] = {
    "MES": {"multiplier": "5",    "exchange": "CME",   "currency": "USD"},
    "MNQ": {"multiplier": "2",    "exchange": "CME",   "currency": "USD"},
    "MGC": {"multiplier": "10",   "exchange": "COMEX", "currency": "USD"},
    "CL":  {"multiplier": "1000", "exchange": "NYMEX", "currency": "USD"},
    "ES":  {"multiplier": "50",   "exchange": "CME",   "currency": "USD"},
    "NQ":  {"multiplier": "20",   "exchange": "CME",   "currency": "USD"},
    "GC":  {"multiplier": "100",  "exchange": "COMEX", "currency": "USD"},
    "RTY": {"multiplier": "50",   "exchange": "CME",   "currency": "USD"},
    "M2K": {"multiplier": "5",    "exchange": "CME",   "currency": "USD"},
}


def _make_contfut(root: str) -> Contract:
    """Continuous back-adjusted contract. endDateTime must be empty string."""
    spec = _CONTRACT_SPECS[root]
    c = Contract()
    c.symbol = root
    c.secType = "CONTFUT"
    c.exchange = spec["exchange"]
    c.currency = spec["currency"]
    return c


def _make_fut(root: str, expiry: str = "") -> Contract:
    """Specific FUT contract. expiry = "YYYYMMDD" or "" for front month."""
    spec = _CONTRACT_SPECS[root]
    c = Contract()
    c.symbol = root
    c.secType = "FUT"
    c.exchange = spec["exchange"]
    c.currency = spec["currency"]
    c.lastTradeDateOrContractMonth = expiry
    c.includeExpired = True
    return c


def _bar_ts_utc(date_val) -> pd.Timestamp:
    """Convert an IBKR bar date to UTC. Handles both tz-naive strings and tz-aware datetimes."""
    ts = pd.Timestamp(date_val)
    if ts.tzinfo is None:
        return ts.tz_localize("America/Chicago").tz_convert("UTC")
    return ts.tz_convert("UTC")


def _bars_to_df(bars: list) -> pd.DataFrame:
    valid = [b for b in bars if b.open > 0]
    if not valid:
        return pd.DataFrame()
    records = [
        {"open": b.open, "high": b.high, "low": b.low, "close": b.close,
         "volume": b.volume, "market": "futures", "source": "ibkr", "adjusted": False}
        for b in valid
    ]
    index = pd.DatetimeIndex([_bar_ts_utc(b.date) for b in valid])
    df = pd.DataFrame(records, index=index)
    df.index.name = "timestamp"
    return df


# ------------------------------------------------------------------
# CONTFUT path (daily / weekly)
# ------------------------------------------------------------------

def _fetch_contfut(ib: IB, root: str, tf: dict, label: str) -> pd.DataFrame:
    """Single request, empty endDateTime. Returns whatever IBKR gives for the duration."""
    print(f"  [{label}] CONTFUT request ({tf['duration']}, {tf['bar_size']})...", flush=True)
    try:
        raw = ib.reqHistoricalData(
            _make_contfut(root),
            endDateTime="",
            durationStr=tf["duration"],
            barSizeSetting=tf["bar_size"],
            whatToShow="TRADES",
            useRTH=tf["use_rth"],
            formatDate=1,
        )
    except Exception:
        log.exception("CONTFUT request failed for %s", label)
        return pd.DataFrame()

    n = sum(1 for b in raw if b.open > 0) if raw else 0
    print(f"  [{label}] {n} bars received", flush=True)
    return _bars_to_df(raw) if raw else pd.DataFrame()


# ------------------------------------------------------------------
# Stitched FUT path (intraday)
# ------------------------------------------------------------------

def _get_contract_chain(ib: IB, root: str, years_back: int = 3, max_age_days: int | None = None) -> list:
    """
    Return expired + currently-active contracts for root, sorted oldest → newest.
    Excludes: future contracts (not yet front month) and contracts older than max_age_days.
    """
    spec = _CONTRACT_SPECS[root]
    template = Contract()
    template.symbol = root
    template.secType = "FUT"
    template.exchange = spec["exchange"]
    template.currency = spec["currency"]
    template.includeExpired = True

    details = ib.reqContractDetails(template)
    if not details:
        raise ValueError(f"No contract details returned for {root}")

    today = datetime.now(tz=timezone.utc)
    today_str = today.strftime("%Y%m%d")

    # Oldest we care about: whichever is more recent — years_back limit or data retention limit
    oldest_by_years = (today - timedelta(days=years_back * 365 + 90)).strftime("%Y%m%d")
    if max_age_days is not None:
        oldest_by_retention = (today - timedelta(days=max_age_days)).strftime("%Y%m%d")
        cutoff = max(oldest_by_years, oldest_by_retention)
    else:
        cutoff = oldest_by_years

    chain = [
        d.contract for d in details
        if cutoff <= d.contract.lastTradeDateOrContractMonth[:8] <= today_str
    ]
    return sorted(chain, key=lambda c: c.lastTradeDateOrContractMonth[:8])


def _fetch_contract_bars(ib: IB, contract: Contract, tf: dict, label: str) -> pd.DataFrame:
    """
    Fetch bars for one specific (possibly expired) FUT contract by stepping
    endDateTime backward from the contract's expiry (or now, if still active).
    """
    expiry_str = contract.lastTradeDateOrContractMonth[:8]
    today_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")

    # For active (un-expired) contracts use now; for expired use expiry + 1 day
    if expiry_str >= today_str:
        end_dt = datetime.now(tz=timezone.utc)
    else:
        end_dt = datetime.strptime(expiry_str, "%Y%m%d").replace(tzinfo=timezone.utc) + timedelta(days=1)

    seen: dict[str, object] = {}
    max_chunks: int = tf["contract_chunks"]
    chunk_days: int = tf["chunk_days"]
    consecutive_empty = 0

    for chunk in range(max_chunks):
        end_str = end_dt.strftime("%Y%m%d %H:%M:%S UTC")
        try:
            raw = ib.reqHistoricalData(
                contract,
                endDateTime=end_str,
                durationStr=tf["duration"],
                barSizeSetting=tf["bar_size"],
                whatToShow="TRADES",
                useRTH=tf["use_rth"],
                formatDate=1,
            )
        except Exception:
            log.exception("reqHistoricalData failed for %s chunk %d", label, chunk)
            break

        added = 0
        if raw:
            for b in raw:
                key = str(b.date)
                if b.open > 0 and key not in seen:
                    seen[key] = b
                    added += 1

        if added == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break  # 3 empty chunks in a row — no more data for this contract
        else:
            consecutive_empty = 0

        end_dt -= timedelta(days=chunk_days)
        ib.sleep(0.3)

    if not seen:
        return pd.DataFrame()
    return _bars_to_df(sorted(seen.values(), key=lambda b: str(b.date)))


def _ratio_stitch(frames: list[pd.DataFrame], label: str = "") -> pd.DataFrame:
    """
    Combine per-contract DataFrames (sorted oldest first) into one continuous
    series using ratio back-adjustment at each roll date.

    At each roll from contract[i] to contract[i+1]:
      ratio = P_new / P_old  (both sampled at the SAME timestamp — the last
      bar common to both contracts). This isolates the spread between the two
      contracts and avoids contaminating the ratio with price trend.

    All bars older than the roll date are multiplied by the accumulated ratio.
    This preserves percentage returns while eliminating price gaps.
    """
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0].copy()

    result = frames[-1].copy()
    cumulative_ratio = 1.0

    for i in range(len(frames) - 2, -1, -1):
        older = frames[i]
        newer = frames[i + 1]

        older_span = f"{older.index.min().date()}→{older.index.max().date()}"
        newer_span = f"{newer.index.min().date()}→{newer.index.max().date()}"

        # Find common timestamps in the overlap period
        common_ts = older.index.intersection(newer.index)

        if not common_ts.empty:
            roll_ts = common_ts[-1]  # last common bar — closest to actual roll
            p_old = older.loc[roll_ts, "close"]
            p_new = newer.loc[roll_ts, "close"]
            method = f"overlap ({len(common_ts)} common bars, roll_ts={roll_ts.date()})"
        else:
            # No overlap — fall back to adjacent endpoints
            p_old = older["close"].iloc[-1]
            p_new = newer["close"].iloc[0]
            method = "NO OVERLAP — endpoint fallback (ratio may be inaccurate)"

        if p_old <= 0:
            log.warning("[%s] roll %d: zero p_old — skipping", label, i)
            continue

        ratio = p_new / p_old
        cumulative_ratio *= ratio

        log.info(
            "[%s] roll %d: older=%s  newer=%s  p_old=%.4f  p_new=%.4f  "
            "ratio=%.6f  cumulative=%.6f  method=%s",
            label, i, older_span, newer_span, p_old, p_new,
            ratio, cumulative_ratio, method,
        )

        adjusted = older.copy()
        for col in ("open", "high", "low", "close"):
            adjusted[col] = (adjusted[col] * cumulative_ratio).round(4)

        # Stitch at roll_ts — continuity is guaranteed there, not at newer_first.
        # Trim result to roll_ts onwards so the overlap period comes from one contract only.
        # Mixing bars from both contracts in the overlap produces oscillating price jumps.
        result = result[result.index >= roll_ts]
        prepend = adjusted[adjusted.index < roll_ts]
        if not prepend.empty:
            result = pd.concat([prepend, result])

    result = result.sort_index()
    result = result[~result.index.duplicated(keep="last")]
    return result


def _seed_stitched(ib: IB, root: str, timeframe: str, tf: dict) -> pd.DataFrame:
    """Full 3-year stitch across all contracts. Called on first run."""
    print(f"  [{root} {timeframe}] Fetching contract chain...", flush=True)
    chain = _get_contract_chain(ib, root, years_back=3, max_age_days=tf["max_contract_age_days"])
    print(f"  [{root} {timeframe}] {len(chain)} contracts to fetch", flush=True)

    frames: list[pd.DataFrame] = []
    for i, contract in enumerate(chain, 1):
        expiry = contract.lastTradeDateOrContractMonth[:8]
        label = f"{root} {timeframe} exp={expiry}"
        print(f"  [{root} {timeframe}] Contract {i}/{len(chain)}: {expiry}", flush=True)

        df = _fetch_contract_bars(ib, contract, tf, label)
        if not df.empty:
            frames.append(df)
            print(f"    {len(df)} bars  ({df.index.min().date()} → {df.index.max().date()})", flush=True)
        else:
            print(f"    no bars", flush=True)

    if not frames:
        return pd.DataFrame()

    print(f"  [{root} {timeframe}] Stitching {len(frames)} contracts...", flush=True)
    return _ratio_stitch(frames, label=f"{root} {timeframe}")


def _update_stitched(ib: IB, root: str, timeframe: str, tf: dict, since: pd.Timestamp) -> pd.DataFrame:
    """Incremental update: fetch only from current front-month contract since last bar."""
    details = ib.reqContractDetails(_make_fut(root))
    if not details:
        log.warning("No front-month contract details for %s", root)
        return pd.DataFrame()

    contract = details[0].contract
    expiry = contract.lastTradeDateOrContractMonth[:8]
    print(f"  [{root} {timeframe}] Incremental from {since.date()} (front month: {expiry})", flush=True)

    # Single chunk from now backward — just need recent bars
    end_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d %H:%M:%S UTC")
    try:
        raw = ib.reqHistoricalData(
            contract,
            endDateTime=end_str,
            durationStr=tf["duration"],
            barSizeSetting=tf["bar_size"],
            whatToShow="TRADES",
            useRTH=tf["use_rth"],
            formatDate=1,
        )
    except Exception:
        log.exception("Incremental fetch failed for %s %s", root, timeframe)
        return pd.DataFrame()

    df = _bars_to_df(raw) if raw else pd.DataFrame()
    if not df.empty:
        df = df[df.index > since]
    return df


# ------------------------------------------------------------------
# Public interface
# ------------------------------------------------------------------

def collect(root: str, timeframe: str = "1D") -> None:
    """Fetch and store bars for one futures root symbol and timeframe."""
    if root not in _CONTRACT_SPECS:
        raise ValueError(f"Unknown root: {root}. Add to _CONTRACT_SPECS.")
    if timeframe not in _TIMEFRAMES:
        raise ValueError(f"Unknown timeframe: {timeframe}. Valid: {list(_TIMEFRAMES)}")

    tf = _TIMEFRAMES[timeframe]
    store = get_store()
    s = get_settings()
    store_key = f"{root}_continuous_{timeframe}"
    now = datetime.now(tz=timezone.utc)
    label = f"{root} {timeframe}"

    has_data = store.has_symbol("futures", store_key)
    if has_data:
        last_bar = store.read_bars("futures", store_key).index.max()
        if last_bar >= now - timedelta(hours=1):
            print(f"  [{label}] Already up to date (last: {last_bar.date()})", flush=True)
            return

    ib = IB()
    try:
        ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id)

        if tf["contfut"]:
            df = _fetch_contfut(ib, root, tf, label)
        elif has_data:
            last_bar = store.read_bars("futures", store_key).index.max()
            df = _update_stitched(ib, root, timeframe, tf, since=last_bar)
        else:
            df = _seed_stitched(ib, root, timeframe, tf)

    finally:
        ib.disconnect()

    if df.empty:
        print(f"  [{label}] No bars returned", flush=True)
        log.warning("No bars for %s %s", root, timeframe)
        return

    if has_data:
        existing_end = store.read_bars("futures", store_key).index.max()
        df = df[df.index > existing_end]

    if df.empty:
        print(f"  [{label}] No new bars", flush=True)
        return

    store.write_bars("futures", store_key, df)
    date_range = f"{df.index.min().date()} → {df.index.max().date()}"
    print(f"  [{label}] Stored {len(df)} bars  ({date_range})", flush=True)
    log.info("Stored %d bars for %s %s", len(df), root, timeframe)


def collect_all(timeframe: str = "1D") -> None:
    """Collect all configured futures symbols for one timeframe."""
    symbols = get_settings().futures_symbols
    for root in symbols:
        try:
            collect(root, timeframe)
        except Exception:
            log.exception("Failed to collect %s %s", root, timeframe)


def collect_all_timeframes() -> None:
    """Full acquisition run across all symbols and timeframes. Use for initial seed."""
    symbols = get_settings().futures_symbols
    timeframes = list(_TIMEFRAMES)
    total = len(symbols) * len(timeframes)
    done = 0

    print(f"\n=== Futures seed: {len(symbols)} symbols × {len(timeframes)} timeframes = {total} jobs ===\n", flush=True)

    for i, tf_key in enumerate(timeframes, 1):
        tf_cfg = _TIMEFRAMES[tf_key]
        mode = "CONTFUT" if tf_cfg["contfut"] else "stitched FUT"
        print(f"── Timeframe {i}/{len(timeframes)}: {tf_key} ({tf_cfg['bar_size']}, {mode}) ──", flush=True)
        for root in symbols:
            try:
                collect(root, tf_key)
            except Exception:
                log.exception("Failed to collect %s %s", root, tf_key)
            done += 1
        print(f"   {done}/{total} jobs done\n", flush=True)

    print("=== Seed complete ===", flush=True)
