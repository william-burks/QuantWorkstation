"""
IBKR futures OHLCV batch collector via ib_insync.

Requires IB Gateway or TWS running locally on the configured port.
Fetches daily bars for the front-month contract of each configured root symbol.
Stores under the continuous symbol key (e.g. "ES_continuous_daily").

IBKR historical data limits:
  Daily bars: up to 1 year per request (use multiple requests for longer history)
  Hourly bars: up to 30 days per request
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from ib_insync import IB, Contract, util

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

# IBKR bar size strings
_BAR_SIZES = {
    "daily": "1 day",
    "hourly": "1 hour",
}

# Duration strings for IBKR historical data requests (max per request)
_DURATIONS = {
    "daily": "1 Y",    # 1 year at a time
    "hourly": "30 D",  # 30 days at a time
}

# Known contract specs — multiplier, exchange, currency
_CONTRACT_SPECS: dict[str, dict] = {
    "ES": {"multiplier": "50", "exchange": "CME", "currency": "USD"},
    "NQ": {"multiplier": "20", "exchange": "CME", "currency": "USD"},
    "CL": {"multiplier": "1000", "exchange": "NYMEX", "currency": "USD"},
    "GC": {"multiplier": "100", "exchange": "COMEX", "currency": "USD"},
}


def _make_contract(root: str) -> Contract:
    spec = _CONTRACT_SPECS[root]
    c = Contract()
    c.symbol = root
    c.secType = "FUT"
    c.exchange = spec["exchange"]
    c.currency = spec["currency"]
    c.lastTradeDateOrContractMonth = ""  # empty = front month
    return c


def _bars_to_df(bars: list, root: str) -> pd.DataFrame:
    records = [
        {
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "market": "futures",
            "source": "ibkr",
            "adjusted": False,
        }
        for b in bars
        if b.open > 0  # IBKR sometimes returns empty bars with 0 prices
    ]
    index = pd.DatetimeIndex(
        [pd.Timestamp(b.date, tz="US/Central").tz_convert("UTC") for b in bars if b.open > 0]
    )
    df = pd.DataFrame(records, index=index)
    df.index.name = "timestamp"
    return df


def collect(root: str, timeframe: str = "daily") -> None:
    """Fetch and store bars for one futures root symbol."""
    if root not in _CONTRACT_SPECS:
        raise ValueError(f"Unknown futures root: {root}. Add to _CONTRACT_SPECS.")

    store = get_store()
    s = get_settings()
    store_key = f"{root}_continuous_{timeframe}"

    now = datetime.now(tz=timezone.utc)

    if store.has_symbol("futures", store_key):
        existing = store.read_bars("futures", store_key)
        start = existing.index.max()
        log.info("Incremental collect %s %s from %s", root, timeframe, start)
    else:
        start = now - timedelta(days=365)
        log.info("Init collect %s %s (1yr)", root, timeframe)

    if start >= now - timedelta(hours=1):
        log.info("No new bars for %s %s", root, timeframe)
        return

    ib = IB()
    try:
        ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id)
        contract = _make_contract(root)
        ib.qualifyContracts(contract)

        end_dt = now.strftime("%Y%m%d %H:%M:%S UTC")
        raw_bars = ib.reqHistoricalData(
            contract,
            endDateTime=end_dt,
            durationStr=_DURATIONS[timeframe],
            barSizeSetting=_BAR_SIZES[timeframe],
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        if not raw_bars:
            log.warning("No data returned for %s %s", root, timeframe)
            return

        df = _bars_to_df(raw_bars, root)
        # Filter to only new bars
        if store.has_symbol("futures", store_key):
            df = df[df.index > start]

        if df.empty:
            log.info("No new bars after dedup for %s %s", root, timeframe)
            return

        store.write_bars("futures", store_key, df)
        log.info("Stored %d bars for %s %s", len(df), root, timeframe)

    finally:
        ib.disconnect()


def collect_all(timeframe: str = "daily") -> None:
    """Collect all configured futures symbols."""
    symbols = get_settings().futures_symbols
    for root in symbols:
        try:
            collect(root, timeframe)
        except Exception:
            log.exception("Failed to collect %s %s", root, timeframe)
