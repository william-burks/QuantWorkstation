"""
Futures continuous series builder using the Panama method.

Panama (ratio-adjusted) roll:
  At each roll, multiply all prior prices by (new_front_close / old_front_close).
  Preserves percentage returns. Prices are not actual tradeable prices.

Usage:
  from data.collectors.roll_calendar import build_continuous
  continuous_df = build_continuous("ES", contracts_df, bars_by_expiry)
"""

import logging
from datetime import date

import pandas as pd

log = logging.getLogger(__name__)

# Roll N days before expiry (standard practice: roll ~5 days before last trade date)
_ROLL_DAYS_BEFORE_EXPIRY = 5


def get_roll_date(expiry: date) -> date:
    """Return the date on which we roll to the next contract."""
    expiry_ts = pd.Timestamp(expiry)
    roll_ts = expiry_ts - pd.offsets.BDay(_ROLL_DAYS_BEFORE_EXPIRY)
    return roll_ts.date()


def build_continuous(
    root: str,
    contracts: pd.DataFrame,
    bars_by_expiry: dict[date, pd.DataFrame],
) -> pd.DataFrame:
    """
    Build a Panama-adjusted continuous price series.

    Args:
        root: futures root symbol, e.g. "ES"
        contracts: DataFrame with columns [expiry, front_month] indexed by expiry date,
                   sorted ascending by expiry
        bars_by_expiry: dict mapping expiry date → DataFrame of OHLCV bars for that contract

    Returns:
        DataFrame with same columns as input bars, DatetimeIndex UTC, adjusted=True,
        continuous_symbol = f"{root}_continuous"
    """
    if contracts.empty:
        raise ValueError(f"No contracts provided for {root}")

    contracts = contracts.sort_values("expiry").reset_index(drop=True)
    segments: list[pd.DataFrame] = []
    cumulative_ratio = 1.0

    for i in range(len(contracts) - 1, -1, -1):
        expiry = contracts.loc[i, "expiry"]
        bars = bars_by_expiry.get(expiry)
        if bars is None or bars.empty:
            log.warning("No bars for %s contract expiring %s — skipping", root, expiry)
            continue

        if i < len(contracts) - 1:
            next_expiry = contracts.loc[i + 1, "expiry"]
            next_bars = bars_by_expiry.get(next_expiry)
            roll_date = get_roll_date(expiry)
            roll_ts = pd.Timestamp(roll_date, tz="UTC")

            # Find the close prices on roll date for ratio calculation
            old_close = _close_on_or_before(bars, roll_ts)
            new_close = _close_on_or_before(next_bars, roll_ts) if next_bars is not None else None

            if old_close and new_close and old_close > 0:
                ratio = new_close / old_close
                cumulative_ratio *= ratio
                log.debug(
                    "Roll %s → next on %s: ratio=%.6f cumulative=%.6f",
                    expiry, roll_date, ratio, cumulative_ratio
                )

            # Trim this contract's bars to its active period
            if i > 0:
                prev_expiry = contracts.loc[i - 1, "expiry"]
                prev_roll = pd.Timestamp(get_roll_date(prev_expiry), tz="UTC")
                bars = bars[bars.index > prev_roll]
            bars = bars[bars.index <= roll_ts]
        else:
            # Most recent contract — use all available bars
            if i > 0:
                prev_expiry = contracts.loc[i - 1, "expiry"]
                prev_roll = pd.Timestamp(get_roll_date(prev_expiry), tz="UTC")
                bars = bars[bars.index > prev_roll]

        if bars.empty:
            continue

        # Apply cumulative adjustment to OHLC (not volume)
        adjusted = bars.copy()
        for col in ("open", "high", "low", "close"):
            if col in adjusted.columns:
                adjusted[col] = adjusted[col] * cumulative_ratio
        adjusted["adjusted"] = True

        segments.append(adjusted)

    if not segments:
        raise ValueError(f"Could not build continuous series for {root} — no valid segments")

    result = pd.concat(segments).sort_index()
    result = result[~result.index.duplicated(keep="last")]
    log.info("Built continuous series for %s: %d bars (%s to %s)",
             root, len(result), result.index.min(), result.index.max())
    return result


def _close_on_or_before(bars: pd.DataFrame, ts: pd.Timestamp) -> float | None:
    """Return the close price on or before timestamp, or None if no data."""
    subset = bars[bars.index <= ts]
    if subset.empty:
        return None
    return float(subset["close"].iloc[-1])
