"""
OHLCV data quality validation.

validate_bars(df, freq) — single public function.
  P1: raises ValueError immediately (bad data, must not write)
  P2: warnings.warn  (gaps, stale feed, schema drift)
  P3: warnings.warn  (low row count)
"""

from __future__ import annotations

import warnings
from datetime import UTC, datetime

import pandas as pd

_REQUIRED_COLS = ["open", "high", "low", "close"]


def _fmt_ts(idx: pd.DatetimeIndex, n: int = 3) -> str:
    """Format up to n timestamps for error messages."""
    return str(list(idx[:n]))


def _price_cols_check(df: pd.DataFrame) -> tuple[bool, str]:
    """Return (ok, error_msg). ok=True means columns present."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Schema drift: missing columns {missing}"
    return True, ""


def _expected_delta(freq: str) -> pd.Timedelta:
    """Convert pandas offset string to expected bar spacing."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        offset = pd.tseries.frequencies.to_offset(freq)
    if offset is None:
        raise ValueError(f"Cannot parse freq: {freq!r}")
    # For fixed-frequency offsets (hours, minutes) use nanos.
    # For calendar-based (days, weeks) fall back to approx timedelta.
    try:
        ns = offset.nanos
        return pd.Timedelta(nanoseconds=ns)
    except (AttributeError, ValueError):
        # Day-based — approximate
        return pd.Timedelta(offset.freqstr)


def validate_bars(df: pd.DataFrame, freq: str) -> None:
    """Validate an OHLCV DataFrame before writing to ArcticDB.

    P1 violations raise ValueError.
    P2/P3 violations emit warnings.warn (stacklevel=2 → points to caller).

    Args:
        df: DataFrame with DatetimeIndex and OHLCV columns.
        freq: pandas offset string for expected bar spacing, e.g. '1H', '1D'.
    """
    if df.empty:
        return

    # ── P2: Schema drift (missing columns) — check before price checks ──
    cols_ok, drift_msg = _price_cols_check(df)
    if not cols_ok:
        warnings.warn(drift_msg, stacklevel=2)
        # No price checks possible without columns — return after drift warn
        return

    # ── P1: UTC timezone ─────────────────────────────────────────────────
    tz = getattr(df.index, "tz", None)
    if tz is None or str(tz) not in ("UTC", "utc"):
        raise ValueError(f"Index timezone must be UTC, got {tz}")

    # ── P1: Unique timestamps ────────────────────────────────────────────
    dupes = df.index[df.index.duplicated()]
    if not dupes.empty:
        raise ValueError(f"Duplicate timestamps: {_fmt_ts(dupes)}")

    # ── P1: No NaN prices ────────────────────────────────────────────────
    nan_mask = df[_REQUIRED_COLS].isna()
    if nan_mask.any().any():
        bad_cols = [c for c in _REQUIRED_COLS if nan_mask[c].any()]
        bad_idx = df.index[nan_mask[bad_cols].any(axis=1)]
        raise ValueError(f"NaN prices in {bad_cols} at {_fmt_ts(bad_idx)}")

    # ── P1: No zero prices ───────────────────────────────────────────────
    zero_mask = df[_REQUIRED_COLS] == 0
    if zero_mask.any().any():
        bad_cols = [c for c in _REQUIRED_COLS if zero_mask[c].any()]
        bad_idx = df.index[zero_mask[bad_cols].any(axis=1)]
        raise ValueError(f"Zero prices in {bad_cols} at {_fmt_ts(bad_idx)}")

    # ── P1: No negative prices ───────────────────────────────────────────
    neg_mask = df[_REQUIRED_COLS] < 0
    if neg_mask.any().any():
        bad_cols = [c for c in _REQUIRED_COLS if neg_mask[c].any()]
        bad_idx = df.index[neg_mask[bad_cols].any(axis=1)]
        raise ValueError(f"Negative prices in {bad_cols} at {_fmt_ts(bad_idx)}")

    # ── P1: high >= low ──────────────────────────────────────────────────
    hl_bad = df.index[df["high"] < df["low"]]
    if not hl_bad.empty:
        raise ValueError(f"OHLCV violation: high < low at {_fmt_ts(hl_bad)}")

    # ── P1: close in [low, high] ─────────────────────────────────────────
    close_bad = df.index[(df["close"] < df["low"]) | (df["close"] > df["high"])]
    if not close_bad.empty:
        raise ValueError(f"OHLCV violation: close out of [low, high] at {_fmt_ts(close_bad)}")

    # ── P1: open in [low, high] ──────────────────────────────────────────
    open_bad = df.index[(df["open"] < df["low"]) | (df["open"] > df["high"])]
    if not open_bad.empty:
        raise ValueError(f"OHLCV violation: open out of [low, high] at {_fmt_ts(open_bad)}")

    # ── P2: Gap detection ────────────────────────────────────────────────
    expected = _expected_delta(freq)
    diffs = df.index.to_series().diff().dropna()
    threshold = expected * 2
    gaps = diffs[diffs > threshold]
    if not gaps.empty:
        first_gap = gaps.index[0]
        warnings.warn(
            f"Gap detected: {len(gaps)} gap(s) > 2× expected spacing ({expected}); "
            f"first at {first_gap}",
            stacklevel=2,
        )

    # ── P2: Stale feed ───────────────────────────────────────────────────
    now = datetime.now(tz=UTC)
    last_bar = df.index.max()
    stale_threshold = expected * 3
    if (now - last_bar) > stale_threshold:
        warnings.warn(
            f"Stale feed: last bar at {last_bar}, expected within {stale_threshold}",
            stacklevel=2,
        )

    # ── P3: Row count vs expected ────────────────────────────────────────
    span = df.index.max() - df.index.min()
    if span > pd.Timedelta(0):
        expected_count = int(span / expected) + 1
        actual_count = len(df)
        if actual_count < expected_count * 0.95:
            warnings.warn(
                f"Row count below 95% of expected: {actual_count} actual vs "
                f"{expected_count} expected for {freq} over {span}",
                stacklevel=2,
            )
