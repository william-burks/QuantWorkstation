"""Shared CSV artifact and simple CLI parsing helpers for strategy scripts."""

from pathlib import Path

import pandas as pd

TRADE_CSV_COLUMNS = [
    'entry_time',
    'sweep_time',
    'direction',
    'session',
    'tf',
    'entry',
    'stop',
    'target',
    'r_dist',
    'exit_price',
    'pnl_r',
    'outcome',
]


def parse_float_list(raw: str) -> list[float]:
    """Parse a comma-separated float list, skipping empty tokens."""
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def parse_str_list(raw: str) -> list[str]:
    """Parse a comma-separated string list, skipping empty tokens."""
    return [x.strip() for x in raw.split(',') if x.strip()]


def normalize_trades_for_csv(trades_df: pd.DataFrame | None) -> pd.DataFrame:
    """Guarantee a stable CSV schema, even when no trades are generated."""
    if trades_df is None or trades_df.empty:
        return pd.DataFrame(columns=TRADE_CSV_COLUMNS)
    return trades_df.copy().reindex(columns=TRADE_CSV_COLUMNS)


def write_results_csv(df: pd.DataFrame, output_csv: str | Path, artifact_name: str = 'results CSV') -> Path:
    """Write CSV artifact to requested path and verify it is non-empty."""
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to write non-empty {artifact_name} at {output_path}")
    return output_path

