from pathlib import Path

import pandas as pd

from strategies.common.strategy_artifacts import (
    TRADE_CSV_COLUMNS,
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


def test_write_results_csv_creates_parent_and_writes_non_empty(tmp_path: Path):
    out_path = tmp_path / 'nested' / 'results.csv'
    df = pd.DataFrame([{'a': 1}])

    written = write_results_csv(df, out_path, artifact_name='test CSV')

    assert written == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0



