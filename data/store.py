"""
arcticdb client wrapper.

Libraries:
  crypto   — crypto OHLCV bars (symbol per ticker, e.g. "BTC/USD")
  futures  — futures OHLCV bars (symbol per continuous ticker, e.g. "ES_continuous")
  futures_meta — FuturesContract metadata (symbol per root, e.g. "ES")
  signals  — strategy signals (symbol = "<strategy>/<ticker>", e.g. "mars/ES_continuous")
"""

import os
from typing import TYPE_CHECKING

import arcticdb as adb
import pandas as pd

if TYPE_CHECKING:
    from arcticdb import Arctic
    from arcticdb.version_store.library import Library

_LIBRARIES = ("crypto", "futures", "futures_meta", "signals")


class Store:
    def __init__(self, uri: str | None = None) -> None:
        uri = uri or os.environ.get("ARCTIC_URI", "lmdb:///data/arctic")
        self._ac: Arctic = adb.Arctic(uri)
        self._libs: dict[str, Library] = {}
        for lib in _LIBRARIES:
            self._libs[lib] = self._ac.get_library(lib, create_if_missing=True)

    # ------------------------------------------------------------------
    # Bars
    # ------------------------------------------------------------------

    def write_bars(self, library: str, symbol: str, df: pd.DataFrame) -> None:
        """Write or append bars. df must have DatetimeIndex (UTC)."""
        lib = self._libs[library]
        if lib.has_symbol(symbol):
            lib.append(symbol, df, prune_previous_version=True)
        else:
            lib.write(symbol, df)

    def read_bars(
        self,
        library: str,
        symbol: str,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        lib = self._libs[library]
        date_range = (start, end) if (start or end) else None
        item = lib.read(symbol, date_range=date_range)
        return item.data

    def list_symbols(self, library: str) -> list[str]:
        return self._libs[library].list_symbols()

    def has_symbol(self, library: str, symbol: str) -> bool:
        return self._libs[library].has_symbol(symbol)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def write_signals(self, strategy: str, symbol: str, df: pd.DataFrame) -> None:
        """df must have DatetimeIndex and a 'direction' column (-1/0/1)."""
        key = f"{strategy}/{symbol}"
        self.write_bars("signals", key, df)

    def read_signals(
        self,
        strategy: str,
        symbol: str,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        key = f"{strategy}/{symbol}"
        return self.read_bars("signals", key, start, end)

    # ------------------------------------------------------------------
    # Futures metadata
    # ------------------------------------------------------------------

    def write_contract_meta(self, root: str, df: pd.DataFrame) -> None:
        """df indexed by expiry date, one row per contract."""
        lib = self._libs["futures_meta"]
        lib.write(root, df, prune_previous_version=True)

    def read_contract_meta(self, root: str) -> pd.DataFrame:
        return self._libs["futures_meta"].read(root).data


# Module-level singleton — import and use directly
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
