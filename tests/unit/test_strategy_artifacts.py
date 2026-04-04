from pathlib import Path

import pandas as pd

from strategies.common.strategy_artifacts import (
    BASELINE_CSV_COLUMNS,
    TRADE_CSV_COLUMNS,
    build_baseline_summary_for_csv,
    normalize_trades_for_csv,
    parse_float_list,
    parse_str_list,
    write_results_csv,
)


def test_parse_helpers():
    assert parse_float_list('1, 2.5, ,3') == [1.0, 2.5, 3.0]
    assert parse_str_list('NY_PRE, LONDON, ,AFTER') == ['NY_PRE', 'LONDON', 'AFTER']


def test_normalize_trades_for_csv_empty():
    empty = normalize_trades_for_csv(pd.DataFrame())
    assert list(empty.columns) == TRADE_CSV_COLUMNS
    assert empty.empty


def test_normalize_trades_for_csv_reindex():
    df = pd.DataFrame([{col: i for i, col in enumerate(TRADE_CSV_COLUMNS)} | {'extra_col': 99}])
    out = normalize_trades_for_csv(df)
    assert list(out.columns) == TRADE_CSV_COLUMNS
    assert 'extra_col' not in out.columns


def test_build_baseline_summary_for_csv_maps_metrics_and_config():
    result = {
        'config': {
            'allowed_sessions': ['NY_PRE', 'LONDON'],
            'allowed_dir': ['BEAR'],
            'target_r': 1.25,
            'wick_mode': 'exclude_q2',
            'atr_mult_stop': 0.5,
            'max_hold_bars': 36,
            'stop_mode': 'sweep_atr',
        },
        'metrics': {
            'sample_size': 60,
            'win_rate': 0.45,
            'avg_r_per_trade': 0.065181,
            'total_r': 3.910844,
            'profit_factor': 1.125,
            'sharpe': 0.930759,
            'max_drawdown_r': -8.410892,
        },
    }

    out = build_baseline_summary_for_csv(
        result,
        instrument='es',
        timeframe='1h',
        direction='BEAR',
        timestamp='2026-04-04T12:34:56Z',
    )

    assert list(out.columns) == BASELINE_CSV_COLUMNS
    row = out.iloc[0].to_dict()
    assert row['instrument'] == 'ES'
    assert row['timeframe'] == '1H'
    assert row['direction'] == 'bear'
    assert row['logic_type'] == 'baseline'
    assert row['allowed_sessions'] == 'NY_PRE,LONDON'
    assert row['allowed_dir'] == 'BEAR'
    assert row['total_trades'] == 60
    assert row['win_rate'] == 0.45
    assert row['avg_r'] == 0.065181
    assert row['total_r'] == 3.910844
    assert row['profit_factor'] == 1.125
    assert row['sharpe'] == 0.930759
    assert row['max_drawdown'] == -8.410892
    assert row['timestamp'] == '2026-04-04T12:34:56Z'


def test_write_results_csv_creates_parent_and_writes_non_empty(tmp_path: Path):
    out_path = tmp_path / 'nested' / 'results.csv'
    df = pd.DataFrame([{'a': 1}])

    written = write_results_csv(df, out_path, artifact_name='test CSV')

    assert written == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0



