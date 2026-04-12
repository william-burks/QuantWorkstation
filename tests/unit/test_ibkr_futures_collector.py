"""
Unit tests for the IBKR futures collector.
IB Gateway connection and ib_insync are fully mocked.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.ibkr_futures import _bars_to_df, collect


def _make_ibkr_bar(date_str: str, price: float = 4800.0) -> MagicMock:
    bar = MagicMock()
    bar.date = date_str  # IBKR returns date as "YYYYMMDD" string
    bar.open = price
    bar.high = price * 1.005
    bar.low = price * 0.995
    bar.close = price
    bar.volume = 5000.0
    return bar


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.ibkr_host = "127.0.0.1"
    s.ibkr_port = 4002
    s.ibkr_client_id = 1
    s.futures_symbols = ["ES", "NQ", "CL", "GC"]
    return s


# ------------------------------------------------------------------
# _bars_to_df
# ------------------------------------------------------------------


def test_bars_to_df_filters_zero_price_bars():
    good = _make_ibkr_bar("20240101", 4800.0)
    bad = _make_ibkr_bar("20240102", 0.0)  # IBKR sometimes returns empty bars
    df = _bars_to_df([good, bad])
    assert len(df) == 1
    assert df["close"].iloc[0] == 4800.0


def test_bars_to_df_columns():
    bar = _make_ibkr_bar("20240101", 4800.0)
    df = _bars_to_df([bar])
    expected_cols = {"open", "high", "low", "close", "volume", "market", "source", "adjusted"}
    assert set(df.columns) >= expected_cols
    assert df["market"].iloc[0] == "futures"
    assert df["source"].iloc[0] == "ibkr"
    assert not df["adjusted"].iloc[0]


def test_bars_to_df_index_is_utc():
    bar = _make_ibkr_bar("20240601", 4800.0)
    df = _bars_to_df([bar])
    assert df.index.tz is not None


# ------------------------------------------------------------------
# collect — unknown root raises
# ------------------------------------------------------------------


def test_collect_unknown_root_raises():
    with pytest.raises(ValueError, match="Unknown root"):
        collect("ZZ", "1D")


# ------------------------------------------------------------------
# collect — init path
# ------------------------------------------------------------------


@patch("data.collectors.ibkr_futures.get_settings")
@patch("data.collectors.ibkr_futures.IB")
@patch("data.collectors.ibkr_futures.get_store")
def test_collect_init_connects_and_writes(mock_get_store, mock_ib_class, mock_get_settings):
    mock_get_settings.return_value = _mock_settings()

    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    ib = MagicMock()
    mock_ib_class.return_value = ib

    mock_bars = [_make_ibkr_bar(f"2024010{i + 1}", 4800.0) for i in range(3)]
    ib.reqHistoricalData.return_value = mock_bars

    collect("ES", "1D")

    ib.connect.assert_called_once_with("127.0.0.1", 4002, clientId=1)
    ib.disconnect.assert_called_once()
    store.write_bars.assert_called_once()

    call_args = store.write_bars.call_args[0]
    assert call_args[0] == "futures"
    assert call_args[1] == "ES_contfut_1D"
    assert len(call_args[2]) == 3


@patch("data.collectors.ibkr_futures.get_settings")
@patch("data.collectors.ibkr_futures.IB")
@patch("data.collectors.ibkr_futures.get_store")
def test_collect_disconnects_on_exception(mock_get_store, mock_ib_class, mock_get_settings):
    """IB.disconnect() must be called even if the connection throws."""
    mock_get_settings.return_value = _mock_settings()

    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    ib = MagicMock()
    mock_ib_class.return_value = ib
    ib.connect.side_effect = RuntimeError("connection lost")

    with pytest.raises(RuntimeError):
        collect("ES", "1D")

    ib.disconnect.assert_called_once()


@patch("data.collectors.ibkr_futures.get_settings")
@patch("data.collectors.ibkr_futures.IB")
@patch("data.collectors.ibkr_futures.get_store")
def test_collect_skips_write_when_no_bars(mock_get_store, mock_ib_class, mock_get_settings):
    mock_get_settings.return_value = _mock_settings()

    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    ib = MagicMock()
    mock_ib_class.return_value = ib
    ib.reqHistoricalData.return_value = []

    collect("ES", "1D")

    store.write_bars.assert_not_called()


# ------------------------------------------------------------------
# collect — incremental path
# ------------------------------------------------------------------


@patch("data.collectors.ibkr_futures.get_settings")
@patch("data.collectors.ibkr_futures.IB")
@patch("data.collectors.ibkr_futures.get_store")
def test_collect_incremental_deduplicates(mock_get_store, mock_ib_class, mock_get_settings):
    """Bars at or before the last stored timestamp should not be written."""
    mock_get_settings.return_value = _mock_settings()

    # "20240601" in US/Central converts to 2024-06-01 05:00:00 UTC
    last_ts = pd.Timestamp("2024-06-01 05:00:00", tz="UTC")
    existing_df = pd.DataFrame(
        {"close": [4800.0]},
        index=pd.DatetimeIndex([last_ts]),
    )

    store = MagicMock()
    store.has_symbol.return_value = True
    store.read_bars.return_value = existing_df
    mock_get_store.return_value = store

    ib = MagicMock()
    mock_ib_class.return_value = ib

    # old_bar converts to last_ts exactly — should be filtered by df.index > start
    # new_bar converts to 2024-06-02 05:00:00 UTC — should be kept
    old_bar = _make_ibkr_bar("20240601", 4800.0)
    new_bar = _make_ibkr_bar("20240602", 4820.0)
    ib.reqHistoricalData.return_value = [old_bar, new_bar]

    collect("ES", "1D")

    write_df = store.write_bars.call_args[0][2]
    assert len(write_df) == 1
    assert write_df["close"].iloc[0] == 4820.0


@patch("data.collectors.ibkr_futures.get_settings")
@patch("data.collectors.ibkr_futures.IB")
@patch("data.collectors.ibkr_futures.get_store")
def test_collect_skips_when_already_up_to_date(mock_get_store, mock_ib_class, mock_get_settings):
    mock_get_settings.return_value = _mock_settings()

    near_now = pd.Timestamp.now(tz="UTC") - timedelta(minutes=30)
    existing_df = pd.DataFrame(
        {"close": [4800.0]},
        index=pd.DatetimeIndex([near_now]),
    )

    store = MagicMock()
    store.has_symbol.return_value = True
    store.read_bars.return_value = existing_df
    mock_get_store.return_value = store

    ib = MagicMock()
    mock_ib_class.return_value = ib

    collect("ES", "1D")

    ib.connect.assert_not_called()
