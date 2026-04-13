# mypy: ignore-errors
"""
Unit tests for the FMP economic calendar collector.
All requests.get calls and store writes are mocked — no live API calls in tests.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.economic_calendar import (
    ARC_LIB,
    ARC_SYMBOL,
    FMP_BASE_URL,
    _empty_df,
    _fetch_calendar,
    collect,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_response(data: list[dict], status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response with FMP-shaped payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _sample_events() -> list[dict]:
    return [
        {
            "event": "FOMC Rate Decision",
            "date": "2024-01-31 14:00:00",
            "previous": 5.25,
            "estimate": 5.5,
            "actual": 5.5,
            "impact": "high",
        },
        {
            "event": "ISM Manufacturing PMI",
            "date": "2024-02-01 15:00:00",
            "previous": 47.4,
            "estimate": 47.0,
            "actual": None,
            "impact": "medium",
        },
        {
            "event": "Initial Jobless Claims",
            "date": "2024-02-08 13:30:00",
            "previous": 218000.0,
            "estimate": 220000.0,
            "actual": 217000.0,
            "impact": "low",
        },
    ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_arc_symbol_value():
    assert ARC_SYMBOL == "ECON_CALENDAR"


def test_arc_lib_value():
    assert ARC_LIB == "calendar"


def test_fmp_base_url():
    assert "financialmodelingprep.com" in FMP_BASE_URL


# ---------------------------------------------------------------------------
# _empty_df
# ---------------------------------------------------------------------------


def test_empty_df_has_correct_columns():
    df = _empty_df()
    expected = ["event_name", "previous", "consensus", "actual", "impact", "is_blackout"]
    assert list(df.columns) == expected


def test_empty_df_is_empty():
    df = _empty_df()
    assert df.empty


def test_empty_df_has_utc_index():
    df = _empty_df()
    assert df.index.tz == UTC


# ---------------------------------------------------------------------------
# _fetch_calendar
# ---------------------------------------------------------------------------


def test_fetch_returns_correct_columns():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    expected = ["event_name", "previous", "consensus", "actual", "impact", "is_blackout"]
    assert list(df.columns) == expected


def test_fetch_index_is_utc_datetime():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_fetch_sorted_ascending():
    # Events in reverse order — output must be ascending
    data = list(reversed(_sample_events()))
    mock_resp = _make_response(data)
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert list(df.index) == sorted(df.index)


def test_fetch_is_blackout_true_for_high_impact():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    high_rows = df[df["impact"] == "high"]
    assert high_rows["is_blackout"].all()


def test_fetch_is_blackout_false_for_non_high():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    non_high = df[df["impact"] != "high"]
    assert not non_high["is_blackout"].any()


def test_fetch_actual_is_nan_for_pre_release():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    # Second event has actual=None — must be NaN, not 0
    ism_row = df[df["event_name"] == "ISM Manufacturing PMI"]
    assert not ism_row.empty
    assert pd.isna(ism_row.iloc[0]["actual"])


def test_fetch_estimate_renamed_to_consensus():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert "consensus" in df.columns
    assert "estimate" not in df.columns


def test_fetch_event_renamed_to_event_name():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert "event_name" in df.columns
    assert "event" not in df.columns


def test_fetch_empty_response_returns_empty_df():
    mock_resp = _make_response([])
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert df.empty


def test_fetch_passes_from_to_apikey_params():
    mock_resp = _make_response(_sample_events())
    with patch(
        "data.collectors.economic_calendar.requests.get", return_value=mock_resp
    ) as mock_get:
        _fetch_calendar("my-key", "2024-01-01", "2024-02-28")

    call_kwargs = mock_get.call_args[1]
    params = call_kwargs["params"]
    assert params["from"] == "2024-01-01"
    assert params["to"] == "2024-02-28"
    assert params["apikey"] == "my-key"


def test_fetch_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        with pytest.raises(Exception, match="403"):
            _fetch_calendar("bad-key", "2024-01-01", "2024-02-28")


def test_fetch_row_count_matches_input():
    mock_resp = _make_response(_sample_events())
    with patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp):
        df = _fetch_calendar("test-key", "2024-01-01", "2024-02-28")

    assert len(df) == len(_sample_events())


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def test_collect_writes_econ_calendar_to_calendar_lib():
    mock_resp = _make_response(_sample_events())
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp),
        patch("data.collectors.economic_calendar.get_store", return_value=mock_store),
        patch("data.collectors.economic_calendar.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fmp_api_key = "test-key"
        collect()

    mock_store.write_series.assert_called_once()
    args = mock_store.write_series.call_args[0]
    assert args[0] == "calendar"
    assert args[1] == "ECON_CALENDAR"


def test_collect_written_df_has_correct_columns_and_utc_index():
    mock_resp = _make_response(_sample_events())
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp),
        patch("data.collectors.economic_calendar.get_store", return_value=mock_store),
        patch("data.collectors.economic_calendar.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fmp_api_key = "test-key"
        collect()

    assert ARC_SYMBOL in written
    df = written[ARC_SYMBOL]
    assert "event_name" in df.columns
    assert "is_blackout" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_collect_skips_write_when_no_events():
    mock_resp = _make_response([])
    mock_store = MagicMock()

    with (
        patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp),
        patch("data.collectors.economic_calendar.get_store", return_value=mock_store),
        patch("data.collectors.economic_calendar.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fmp_api_key = "test-key"
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_is_blackout_all_true_for_high_impact_only():
    """is_blackout column must be True for high-impact rows, False for others."""
    mock_resp = _make_response(_sample_events())
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp),
        patch("data.collectors.economic_calendar.get_store", return_value=mock_store),
        patch("data.collectors.economic_calendar.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fmp_api_key = "test-key"
        collect()

    df = written[ARC_SYMBOL]
    assert df[df["impact"] == "high"]["is_blackout"].all()
    assert not df[df["impact"] != "high"]["is_blackout"].any()


def test_collect_actual_nan_preserved_not_coerced_to_zero():
    """actual=None from FMP must be stored as NaN, not 0."""
    mock_resp = _make_response(_sample_events())
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.economic_calendar.requests.get", return_value=mock_resp),
        patch("data.collectors.economic_calendar.get_store", return_value=mock_store),
        patch("data.collectors.economic_calendar.get_settings") as mock_settings,
    ):
        mock_settings.return_value.fmp_api_key = "test-key"
        collect()

    df = written[ARC_SYMBOL]
    ism_row = df[df["event_name"] == "ISM Manufacturing PMI"]
    assert not ism_row.empty
    assert pd.isna(ism_row.iloc[0]["actual"])
