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

BASELINE_CSV_COLUMNS = [
    'instrument',
    'timeframe',
    'direction',
    'logic_type',
    'allowed_dir',
    'allowed_sessions',
    'atr_mult_stop',
    'chain_mode',
    'lh_buffer_mult',
    'lh_lookback',
    'max_hold_bars',
    'min_r_dist',
    'partial_exit_r',
    'stall_bars',
    'stall_threshold',
    'stop_mode',
    'target_r',
    'wick_mode',
    'total_trades',
    'win_rate',
    'avg_r',
    'total_r',
    'profit_factor',
    'sharpe',
    'max_drawdown',
    'timestamp',
]

BASELINE_CONFIG_COLUMNS = [
    'allowed_dir',
    'allowed_sessions',
    'atr_mult_stop',
    'chain_mode',
    'lh_buffer_mult',
    'lh_lookback',
    'max_hold_bars',
    'min_r_dist',
    'partial_exit_r',
    'stall_bars',
    'stall_threshold',
    'stop_mode',
    'target_r',
    'wick_mode',
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


def _csv_scalar(value):
    """Convert list-like values to CSV-friendly scalars."""
    if isinstance(value, (list, tuple, set)):
        return ','.join(str(item) for item in value)
    return value


def build_baseline_summary_for_csv(
    result: dict,
    *,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str = 'baseline',
    timestamp: str | None = None,
) -> pd.DataFrame:
    """Build a one-row parser-compatible baseline summary CSV payload."""
    config = dict(result.get('config') or {})
    metrics = dict(result.get('metrics') or {})

    row = {column: None for column in BASELINE_CSV_COLUMNS}
    row.update({
        'instrument': instrument.upper(),
        'timeframe': timeframe.upper(),
        'direction': direction.lower(),
        'logic_type': logic_type.lower().replace('_', '-'),
        'total_trades': metrics.get('sample_size', 0),
        'win_rate': metrics.get('win_rate'),
        'avg_r': metrics.get('avg_r_per_trade'),
        'total_r': metrics.get('total_r'),
        'profit_factor': metrics.get('profit_factor'),
        'sharpe': metrics.get('sharpe'),
        'max_drawdown': metrics.get('max_drawdown_r'),
        'timestamp': timestamp or pd.Timestamp.now(tz='UTC').isoformat().replace('+00:00', 'Z'),
    })

    for column in BASELINE_CONFIG_COLUMNS:
        if column in config:
            row[column] = _csv_scalar(config[column])

    return pd.DataFrame([row], columns=BASELINE_CSV_COLUMNS)


def write_results_csv(
    df: pd.DataFrame, output_csv: str | Path, artifact_name: str = 'results CSV'
) -> Path:
    """Write CSV artifact to requested path and verify it is non-empty."""
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to write non-empty {artifact_name} at {output_path}")
    return output_path

