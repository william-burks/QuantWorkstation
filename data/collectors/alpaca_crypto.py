"""
Alpaca crypto OHLCV batch collector.

Init run: fetches 2 years of multi-timeframe bars per symbol.
Incremental run: fetches bars since the last stored timestamp.
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from data.config import get_settings
from data.store import get_store

log = logging.getLogger(__name__)

_TWO_YEARS = timedelta(days=730)
_TIMEFRAMES = {
    "1T": TimeFrame(1, TimeFrameUnit.Minute),
    "5T": TimeFrame(5, TimeFrameUnit.Minute),
    "15T": TimeFrame(15, TimeFrameUnit.Minute),
    "1H": TimeFrame(1, TimeFrameUnit.Hour),
    "4H": TimeFrame(4, TimeFrameUnit.Hour),
    "1D": TimeFrame(1, TimeFrameUnit.Day),
    "1W": TimeFrame(1, TimeFrameUnit.Week),
}


def _client() -> CryptoHistoricalDataClient:
    s = get_settings()
    return CryptoHistoricalDataClient(s.alpaca_api_key, s.alpaca_api_secret)


def _bars_to_df(bars: list) -> pd.DataFrame:
    """Normalize a list of Alpaca Bar objects to a plain DataFrame."""
    records = [
        {
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "market": "crypto",
            "source": "alpaca",
            "adjusted": False,
        }
        for b in bars
    ]
    df = pd.DataFrame(records, index=pd.DatetimeIndex([b.timestamp for b in bars], tz="UTC"))
    df.index.name = "timestamp"
    return df


def collect(symbol: str, timeframe: str = "daily") -> None:
    """Fetch and store bars for one symbol. Incremental if data exists."""
    store = get_store()
    tf = _TIMEFRAMES[timeframe]
    lib = "crypto"
    store_key = f"{symbol}_{timeframe}"

    now = datetime.now(tz=UTC)

    if store.has_symbol(lib, store_key):
        existing = store.read_bars(lib, store_key)
        start = existing.index.max() + timedelta(minutes=1)
        log.info("Incremental collect %s %s from %s", symbol, timeframe, start)
    else:
        start = now - _TWO_YEARS
        log.info("Init collect %s %s from %s", symbol, timeframe, start)

    if start >= now - timedelta(hours=1):
        log.info("No new bars for %s %s", symbol, timeframe)
        return

    client = _client()
    request = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=start,
        end=now,
    )
    response = client.get_crypto_bars(request)

    # BarSet exposes data via .data dict — does not support `in` or `[]` directly
    bars = response.data.get(symbol)
    if not bars:
        log.info("Already up to date: no new bars for %s %s", symbol, timeframe)
        return

    df = _bars_to_df(bars)
    store.write_bars(lib, store_key, df)
    log.info("Stored %d bars for %s %s", len(df), symbol, timeframe)


def collect_all(timeframe: str = "daily") -> None:
    """Collect all configured crypto symbols."""
    from data.config import get_settings

    symbols = get_settings().crypto_symbols
    for symbol in symbols:
        try:
            collect(symbol, timeframe)
        except Exception:
            log.exception("Failed to collect %s %s", symbol, timeframe)
