# mypy: ignore-errors
"""
Unit tests for the FRED macro collector.
All fredapi calls and store writes are mocked — no live API calls in tests.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.fred import (
    DEFAULT_SERIES,
    _arc_key,
    _fetch_series,
    collect,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fred_series(dates: list[str], values: list[float]) -> pd.Series:
    """Build a mock pd.Series as fredapi would return (naive DatetimeIndex)."""
    idx = pd.to_datetime(dates)
    return pd.Series(values, index=idx)


def _make_mock_fred(series_data: dict[str, pd.Series]) -> MagicMock:
    """Return a mock fredapi.Fred client that returns pre-built series."""
    mock = MagicMock()
    mock.get_series.side_effect = lambda sid, **kwargs: series_data[sid]
    return mock


# ---------------------------------------------------------------------------
# _arc_key
# ---------------------------------------------------------------------------


def test_arc_key_format():
    assert _arc_key("DGS10") == "DGS10_1D"
    assert _arc_key("BAMLH0A0HYM2") == "BAMLH0A0HYM2_1D"
    assert _arc_key("T10Y2Y") == "T10Y2Y_1D"


# ---------------------------------------------------------------------------
# _fetch_series
# ---------------------------------------------------------------------------


def test_fetch_series_returns_single_value_column():
    raw = _make_fred_series(["2024-01-02", "2024-01-03"], [4.1, 4.15])
    mock_fred = _make_mock_fred({"DGS10": raw})

    df = _fetch_series(mock_fred, "DGS10", None)

    assert list(df.columns) == ["value"]
    assert len(df) == 2


def test_fetch_series_index_is_utc_datetime():
    raw = _make_fred_series(["2024-01-02", "2024-01-03"], [4.1, 4.15])
    mock_fred = _make_mock_fred({"DGS10": raw})

    df = _fetch_series(mock_fred, "DGS10", None)

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_fetch_series_drops_nan_rows():
    raw = _make_fred_series(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        [float("nan"), 4.1, 4.15],
    )
    mock_fred = _make_mock_fred({"DGS10": raw})

    df = _fetch_series(mock_fred, "DGS10", None)

    assert len(df) == 2
    assert not df["value"].isna().any()


def test_fetch_series_passes_observation_start():
    raw = _make_fred_series(["2024-06-01"], [4.5])
    mock_fred = _make_mock_fred({"DGS10": raw})

    _fetch_series(mock_fred, "DGS10", "2024-06-01")

    mock_fred.get_series.assert_called_once_with("DGS10", observation_start="2024-06-01")


def test_fetch_series_no_observation_start_when_none():
    raw = _make_fred_series(["2024-01-02"], [4.1])
    mock_fred = _make_mock_fred({"DGS10": raw})

    _fetch_series(mock_fred, "DGS10", None)

    call_kwargs = mock_fred.get_series.call_args[1]
    assert "observation_start" not in call_kwargs


# ---------------------------------------------------------------------------
# collect — with mocked fredapi + store
# ---------------------------------------------------------------------------


def _build_series_data() -> dict[str, pd.Series]:
    return {
        "DGS2":          _make_fred_series(["2024-01-02", "2024-01-03"], [4.2, 4.25]),
        "DGS10":         _make_fred_series(["2024-01-02", "2024-01-03"], [4.0, 4.05]),
        "T10Y2Y":        _make_fred_series(["2024-01-02", "2024-01-03"], [-0.2, -0.2]),
        "VIXCLS":        _make_fred_series(["2024-01-02", "2024-01-03"], [13.1, 12.8]),
        "BAMLH0A0HYM2":  _make_fred_series(["2024-01-02", "2024-01-03"], [3.5, 3.6]),
    }


def test_collect_writes_all_five_series():
    """collect() calls store.write_series() once per default series."""
    series_data = _build_series_data()
    mock_fred_instance = _make_mock_fred(series_data)
    mock_fred_module = MagicMock()
    mock_fred_module.Fred.return_value = mock_fred_instance

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch.dict("sys.modules", {"fredapi": mock_fred_module}),
        patch("data.collectors.fred.get_store", return_value=mock_store),
        patch("data.collectors.fred.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fred_api_key = "test-key"
        mock_settings.return_value.fred_series = list(DEFAULT_SERIES)
        collect()

    calls = mock_store.write_series.call_args_list
    assert len(calls) == 5

    keys_written = {c[0][1] for c in calls}
    assert keys_written == {"DGS2_1D", "DGS10_1D", "T10Y2Y_1D", "VIXCLS_1D", "BAMLH0A0HYM2_1D"}

    libs = {c[0][0] for c in calls}
    assert libs == {"macro"}


def test_collect_written_df_has_value_column_and_datetime_index():
    """DataFrames written to store have 'value' column and DatetimeIndex."""
    series_data = _build_series_data()
    mock_fred_instance = _make_mock_fred(series_data)
    mock_fred_module = MagicMock()
    mock_fred_module.Fred.return_value = mock_fred_instance

    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch.dict("sys.modules", {"fredapi": mock_fred_module}),
        patch("data.collectors.fred.get_store", return_value=mock_store),
        patch("data.collectors.fred.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fred_api_key = "test-key"
        mock_settings.return_value.fred_series = ["DGS10", "VIXCLS"]
        collect()

    for key in ["DGS10_1D", "VIXCLS_1D"]:
        assert key in written, f"{key} not written"
        df = written[key]
        assert list(df.columns) == ["value"], f"Unexpected columns for {key}: {list(df.columns)}"
        assert pd.api.types.is_datetime64_any_dtype(df.index), "Index must be datetime"


def test_collect_incremental_passes_observation_start():
    """If existing data present, collect uses last date + 1 day as start."""
    existing_df = pd.DataFrame(
        {"value": [4.0]},
        index=pd.to_datetime(["2024-01-03"]).tz_localize("UTC"),
    )

    series_data = {
        "DGS10": _make_fred_series(["2024-01-04"], [4.05]),
    }
    mock_fred_instance = _make_mock_fred(series_data)
    mock_fred_module = MagicMock()
    mock_fred_module.Fred.return_value = mock_fred_instance

    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df

    with (
        patch.dict("sys.modules", {"fredapi": mock_fred_module}),
        patch("data.collectors.fred.get_store", return_value=mock_store),
        patch("data.collectors.fred.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fred_api_key = "test-key"
        mock_settings.return_value.fred_series = ["DGS10"]
        collect()

    call_kwargs = mock_fred_instance.get_series.call_args[1]
    assert call_kwargs.get("observation_start") == "2024-01-04"


def test_collect_skips_empty_result():
    """If FRED returns empty series, write_series is not called."""
    mock_fred_instance = MagicMock()
    mock_fred_instance.get_series.return_value = pd.Series(
        [], index=pd.DatetimeIndex([]), dtype=float
    )
    mock_fred_module = MagicMock()
    mock_fred_module.Fred.return_value = mock_fred_instance

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch.dict("sys.modules", {"fredapi": mock_fred_module}),
        patch("data.collectors.fred.get_store", return_value=mock_store),
        patch("data.collectors.fred.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fred_api_key = "test-key"
        mock_settings.return_value.fred_series = ["DGS10"]
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_raises_if_fredapi_not_installed():
    """ImportError raised with clear message if fredapi is missing."""
    with patch.dict("sys.modules", {"fredapi": None}):
        with pytest.raises(ImportError, match="fredapi package not installed"):
            collect()


# ---------------------------------------------------------------------------
# DEFAULT_SERIES coverage
# ---------------------------------------------------------------------------


def test_default_series_has_five_expected_ids():
    expected = {"DGS2", "DGS10", "T10Y2Y", "VIXCLS", "BAMLH0A0HYM2"}
    assert set(DEFAULT_SERIES) == expected
