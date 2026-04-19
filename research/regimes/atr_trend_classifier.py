"""ATR+ADX rule-based regime classifier.

Produces a 4-label categorical Series per symbol/timeframe and writes to the
ArcticDB signals lib as ``regime_atr/<symbol>_<tf>``.

Labels:
    crisis             — ATR z-score > 2.0 AND ADX > 40
    high_vol_trending  — ATR z-score > 0.5 AND ADX > 25  (not crisis)
    low_vol_ranging    — ATR z-score < 0  AND ADX < 20
    transitional       — all other bars

Thresholds are fixed per QWS-1403 — no tuning in this story.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import numpy as np
import pandas as pd

from data.store import Store

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABELS = ["crisis", "high_vol_trending", "low_vol_ranging", "transitional"]
LABEL_DTYPE = pd.CategoricalDtype(categories=LABELS, ordered=False)

ATR_PERIOD = 14
ADX_PERIOD = 14
ZSCORE_WINDOW = 20

MAX_SINGLE_LABEL_FRACTION = 0.80

# Symbol → ArcticDB library key mapping
_SYMBOL_LIBS: dict[str, tuple[str, str]] = {
    "CL": ("futures", "CL_1H"),
    "MES": ("futures", "MES_1H"),
    "BTC/USD": ("crypto", "BTC/USD_1H"),
}


# ---------------------------------------------------------------------------
# ATR (Wilder's smoothed)
# ---------------------------------------------------------------------------


def _wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed ATR using EWM with alpha=1/period."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Standard 14-period ADX."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = _wilder_atr(high, low, close, period)

    plus_di = (
        pd.Series(plus_dm, index=high.index)
        .ewm(alpha=1.0 / period, min_periods=period, adjust=False)
        .mean()
        / atr
        * 100
    )
    minus_di = (
        pd.Series(minus_dm, index=high.index)
        .ewm(alpha=1.0 / period, min_periods=period, adjust=False)
        .mean()
        / atr
        * 100
    )

    di_sum = plus_di + minus_di
    dx = (plus_di - minus_di).abs() / di_sum.replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx


# ---------------------------------------------------------------------------
# ATR z-score
# ---------------------------------------------------------------------------


def _atr_zscore(atr: pd.Series, window: int) -> pd.Series:
    """Rolling z-score of ATR over `window` bars."""
    roll_mean = atr.rolling(window=window, min_periods=window).mean()
    roll_std = atr.rolling(window=window, min_periods=window).std(ddof=1)
    return (atr - roll_mean) / roll_std.replace(0, np.nan)


# ---------------------------------------------------------------------------
# Label assignment
# ---------------------------------------------------------------------------


def classify(df: pd.DataFrame) -> pd.Series:
    """Compute regime labels for an OHLCV DataFrame.

    Parameters
    ----------
    df:
        DataFrame with columns ``open``, ``high``, ``low``, ``close``
        and a DatetimeIndex.

    Returns
    -------
    pd.Series of CategoricalDtype with 4 levels.
    """
    required = {"high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV DataFrame missing columns: {missing}")

    atr = _wilder_atr(df["high"], df["low"], df["close"], ATR_PERIOD)
    z = _atr_zscore(atr, ZSCORE_WINDOW)
    adx = _adx(df["high"], df["low"], df["close"], ADX_PERIOD)

    # Assign labels in priority order (crisis first)
    label = pd.Series("transitional", index=df.index, dtype=object)
    label = label.where(~((z > 2.0) & (adx > 40)), other="crisis")
    label = label.where(~((z > 0.5) & (adx > 25) & (label != "crisis")), other="high_vol_trending")
    label = label.where(
        ~((z < 0) & (adx < 20) & (label == "transitional")), other="low_vol_ranging"
    )

    return label.astype(LABEL_DTYPE)


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


def _check_distribution(series: pd.Series, symbol_tf: str) -> None:
    """Raise if any single label exceeds MAX_SINGLE_LABEL_FRACTION."""
    counts = series.value_counts(normalize=True)
    for label, fraction in counts.items():
        if fraction > MAX_SINGLE_LABEL_FRACTION:
            raise ValueError(
                f"{symbol_tf}: label '{label}' = {fraction:.1%} — exceeds "
                f"{MAX_SINGLE_LABEL_FRACTION:.0%} guard. Check data quality."
            )


# ---------------------------------------------------------------------------
# Run classifier for one symbol/tf
# ---------------------------------------------------------------------------


def run(symbol: str, tf: str) -> None:
    """Load bars, classify, check distribution, write to signals lib, print summary."""
    store = Store()

    if symbol not in _SYMBOL_LIBS:
        raise ValueError(f"Unknown symbol: {symbol!r}. Supported: {list(_SYMBOL_LIBS.keys())}")

    lib, bar_key = _SYMBOL_LIBS[symbol]
    # Override tf suffix in bar key for flexibility (story currently only needs 1H)
    # Reconstruct key with requested tf
    root = bar_key.rsplit("_", 1)[0]  # e.g. "CL" from "CL_1H"
    actual_bar_key = f"{root}_{tf}"

    df = store.read_bars(lib, actual_bar_key)
    if df.empty:
        raise RuntimeError(f"No bars found for {actual_bar_key} in lib {lib!r}")

    labels = classify(df)
    symbol_tf = f"{symbol}_{tf}"
    _check_distribution(labels, symbol_tf)

    # Write regime labels — full overwrite (regime series are always recalculated in full).
    # ArcticDB does not support categorical dtype — store as string.
    # Use overwrite_bars on signals lib to avoid schema conflicts on re-seed.
    signal_df = labels.astype(str).rename("label").to_frame()
    arc_key = f"regime_atr/{symbol_tf}"
    store.overwrite_bars("signals", arc_key, signal_df)

    # Print distribution
    n = len(labels)
    dist = labels.value_counts(normalize=True).sort_index()
    dist_str = "  ".join(f"{lbl}={frac:.1%}" for lbl, frac in dist.items())
    print(f"{symbol_tf} — {n:,} bars labeled. Distribution: {dist_str}")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ATR+ADX regime classifier — writes to ArcticDB signals lib"
    )
    parser.add_argument(
        "--symbol",
        required=True,
        choices=list(_SYMBOL_LIBS.keys()),
        help="Symbol to classify (e.g. CL, MES, BTC/USD)",
    )
    parser.add_argument(
        "--tf",
        default="1H",
        help="Timeframe (default: 1H)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run(args.symbol, args.tf)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
