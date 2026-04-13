"""
arcticdb client wrapper.

Libraries:
  crypto       — crypto OHLCV bars (symbol per ticker, e.g. "BTC/USD")
  futures      — futures OHLCV bars:
                   stitched intraday: "{ROOT}_{TF}"          e.g. "MES_1H"
                   CONTFUT daily/wk:  "{ROOT}_contfut_{TF}"  e.g. "MES_contfut_1D"
                   cash index:        "{SYMBOL}_idx_{TF}"    e.g. "VIX_idx_1D"
  futures_meta — FuturesContract metadata (symbol per root, e.g. "ES")
  signals      — strategy signals (symbol = "<strategy>/<ticker>")
"""

import os
import re
from typing import TYPE_CHECKING

import arcticdb as adb
import pandas as pd

if TYPE_CHECKING:
    from arcticdb import Arctic
    from arcticdb.version_store.library import Library

_LIBRARIES = ("crypto", "futures", "futures_meta", "signals", "calendar")

_FUTURES_KEY_RE = re.compile(
    r"^[A-Z0-9]+(?:_contfut|_idx)?_(?:5min|10min|15min|30min|1H|2H|4H|8H|1D|1W|1M)$"
)


class Store:
    def __init__(self, uri: str | None = None) -> None:
        default_path = os.path.join(os.path.dirname(__file__), "..", "arctic_data")
        default_uri = f"lmdb://{os.path.abspath(default_path)}"
        uri = uri or os.environ.get("ARCTIC_URI", default_uri)
        self._ac: Arctic = adb.Arctic(uri)
        self._libs: dict[str, Library] = {}
        for lib in _LIBRARIES:
            self._libs[lib] = self._ac.get_library(lib, create_if_missing=True)

    # ------------------------------------------------------------------
    # Bars
    # ------------------------------------------------------------------

    def write_bars(self, library: str, symbol: str, df: pd.DataFrame) -> None:
        """Write or append bars. df must have DatetimeIndex (UTC)."""
        if library == "futures" and not _FUTURES_KEY_RE.match(symbol):
            raise ValueError(
                f"Invalid futures key: {symbol!r}. "
                "Expected '{ROOT}_{TF}' (stitched), '{ROOT}_contfut_{TF}' (CONTFUT), "
                "or '{SYMBOL}_idx_{TF}' (cash index). "
                "Valid TF values: 5min, 10min, 15min, 30min, 1H, 2H, 4H, 8H, 1D, 1W, 1M."
            )
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
        return list(self._libs[library].list_symbols())

    def has_symbol(self, library: str, symbol: str) -> bool:
        return bool(self._libs[library].has_symbol(symbol))

    def _get_lib(self, library: str) -> "Library":
        """Return library handle, creating it if it does not exist."""
        if library not in self._libs:
            self._libs[library] = self._ac.get_library(library, create_if_missing=True)
        return self._libs[library]

    # ------------------------------------------------------------------
    # Series (non-OHLCV)
    # ------------------------------------------------------------------

    def write_series(self, lib: str, symbol: str, df: pd.DataFrame) -> None:
        """Write or append a non-OHLCV time series.

        df must have a DatetimeIndex.  Idempotent: overlapping rows are
        deduplicated by index before writing so no duplicate entries accumulate.
        """
        library = self._get_lib(lib)
        if library.has_symbol(symbol):
            existing = library.read(symbol).data
            combined = pd.concat([existing, df])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            library.write(symbol, combined)
        else:
            library.write(symbol, df)

    def read_series(
        self,
        lib: str,
        symbol: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Read a non-OHLCV time series.

        start/end are optional ISO date strings (e.g. "2024-01-01").
        """
        library = self._get_lib(lib)
        ts_start = pd.Timestamp(start) if start else None
        ts_end = pd.Timestamp(end) if end else None
        date_range = (ts_start, ts_end) if (ts_start is not None or ts_end is not None) else None
        return library.read(symbol, date_range=date_range).data

    def list_instruments(self, library: str) -> list[tuple[str, str]]:
        """Return (root, timeframe) tuples for all symbols in the library.

        For futures keys: "MES_1H" → ("MES", "1H"), "MES_contfut_1D" → ("MES", "1D").
        For other libraries: (symbol, "").
        """
        result: list[tuple[str, str]] = []
        for sym in self.list_symbols(library):
            m = _FUTURES_KEY_RE.match(sym)
            if m:
                # Strip _contfut_ or _idx_ infix and extract TF suffix
                tf_match = re.search(r"_(5min|10min|15min|30min|1H|2H|4H|8H|1D|1W|1M)$", sym)
                tf = tf_match.group(1) if tf_match else ""
                _tf_pat = r"(?:_contfut|_idx)?_(?:5min|10min|15min|30min|1H|2H|4H|8H|1D|1W|1M)$"
                root = re.sub(_tf_pat, "", sym)
                result.append((root, tf))
            else:
                result.append((sym, ""))
        return result

    def symbol_meta(self, library: str, symbol: str) -> dict[str, object]:
        """Return {"rows": int, "last_ts": pd.Timestamp | None} for a symbol."""
        df = self.read_bars(library, symbol)
        rows = len(df)
        last_ts: pd.Timestamp | None = df.index[-1] if rows > 0 else None
        return {"rows": rows, "last_ts": last_ts}

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
