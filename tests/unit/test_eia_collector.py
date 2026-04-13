# mypy: ignore-errors
"""
Unit tests for the EIA crude oil inventory collector.
All requests.get calls and store writes are mocked — no live API calls in tests.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.eia import (
    DEFAULT_SERIES,
    _arc_key,
    _fetch_series,
    collect,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_eia_response(series_id: str, rows: list[dict]) -> MagicMock:
    """Build a mock requests.Response for EIA API data."""
    payload = {
        "response": {
            "data": rows,
        }
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_rows(dates: list[str], values: list[float]) -> list[dict]:
    return [{"period": d, "value": str(v)} for d, v in zip(dates, values)]


# ---------------------------------------------------------------------------
# _arc_key
# ---------------------------------------------------------------------------


def test_arc_key_format():
    assert _arc_key("WCRSTUS1") == "EIA_WCRSTUS1"
    assert _arc_key("WCSSTUS1") == "EIA_WCSSTUS1"
    assert _arc_key("WGTSTUS1") == "EIA_WGTSTUS1"
    assert _arc_key("WDISTUS1") == "EIA_WDISTUS1"


# ---------------------------------------------------------------------------
# _fetch_series
# ---------------------------------------------------------------------------


def test_fetch_series_returns_value_and_surprise_columns():
    rows = _make_rows(["2024-01-05", "2024-01-12"], [420000.0, 422000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "WCRSTUS1", None)

    assert set(df.columns) == {"value", "surprise"}
    assert len(df) == 2


def test_fetch_series_surprise_is_week_over_week_diff():
    rows = _make_rows(["2024-01-05", "2024-01-12", "2024-01-19"], [420000.0, 422000.0, 419000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "WCRSTUS1", None)

    assert pd.isna(df["surprise"].iloc[0])  # first row has no prior week
    assert df["surprise"].iloc[1] == pytest.approx(2000.0)
    assert df["surprise"].iloc[2] == pytest.approx(-3000.0)


def test_fetch_series_index_is_utc_datetime():
    rows = _make_rows(["2024-01-05", "2024-01-12"], [420000.0, 422000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "WCRSTUS1", None)

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_fetch_series_empty_response_returns_empty_df():
    mock_resp = _make_eia_response("WCRSTUS1", [])

    with patch("data.collectors.eia.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "WCRSTUS1", None)

    assert df.empty
    assert set(df.columns) == {"value", "surprise"}


def test_fetch_series_passes_start_date_param():
    rows = _make_rows(["2024-06-07"], [430000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "WCRSTUS1", "2024-06-07")

    call_params = mock_get.call_args[1]["params"]
    assert call_params.get("start") == "2024-06-07"


def test_fetch_series_no_start_param_when_none():
    rows = _make_rows(["2024-01-05"], [420000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "WCRSTUS1", None)

    call_params = mock_get.call_args[1]["params"]
    assert "start" not in call_params


def test_fetch_series_sorted_ascending():
    # Reverse order in response — should be sorted asc by index
    rows = _make_rows(["2024-01-12", "2024-01-05"], [422000.0, 420000.0])
    mock_resp = _make_eia_response("WCRSTUS1", rows)

    with patch("data.collectors.eia.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "WCRSTUS1", None)

    assert df.index[0] < df.index[1]


# ---------------------------------------------------------------------------
# collect — with mocked requests + store
# ---------------------------------------------------------------------------


def _build_mock_response_for(series_id: str) -> MagicMock:
    rows = _make_rows(["2024-01-05", "2024-01-12"], [420000.0, 422000.0])
    return _make_eia_response(series_id, rows)


def test_collect_writes_all_four_series():
    """collect() calls store.write_series() once per default series."""
    responses = {sid: _build_mock_response_for(sid) for sid in DEFAULT_SERIES}
    call_count = [0]

    def mock_get(url, params=None, timeout=None):
        series_param = params.get("facets[series][]", "")
        sid = series_param.replace("PET.", "").replace(".W", "")
        call_count[0] += 1
        return responses.get(sid, _make_eia_response(sid, []))

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.eia.requests.get", side_effect=mock_get),
        patch("data.collectors.eia.get_store", return_value=mock_store),
        patch("data.collectors.eia.get_settings") as mock_settings,
    ):
        mock_settings.return_value.eia_api_key = "test-key"
        mock_settings.return_value.eia_series = list(DEFAULT_SERIES)
        collect()

    calls = mock_store.write_series.call_args_list
    assert len(calls) == 4

    keys_written = {c[0][1] for c in calls}
    assert keys_written == {
        "EIA_WCRSTUS1",
        "EIA_WCSSTUS1",
        "EIA_WGTSTUS1",
        "EIA_WDISTUS1",
    }

    libs = {c[0][0] for c in calls}
    assert libs == {"macro"}


def test_collect_written_df_has_value_and_surprise_columns():
    """DataFrames written to store have 'value' and 'surprise' columns and DatetimeIndex."""
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    def mock_get(url, params=None, timeout=None):
        series_param = params.get("facets[series][]", "")
        sid = series_param.replace("PET.", "").replace(".W", "")
        rows = _make_rows(["2024-01-05", "2024-01-12"], [420000.0, 422000.0])
        return _make_eia_response(sid, rows)

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.eia.requests.get", side_effect=mock_get),
        patch("data.collectors.eia.get_store", return_value=mock_store),
        patch("data.collectors.eia.get_settings") as mock_settings,
    ):
        mock_settings.return_value.eia_api_key = "test-key"
        mock_settings.return_value.eia_series = ["WCRSTUS1"]
        collect()

    assert "EIA_WCRSTUS1" in written
    df = written["EIA_WCRSTUS1"]
    assert "value" in df.columns
    assert "surprise" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_collect_incremental_passes_start_date():
    """If existing data present, collect uses last date + 1 day as start."""
    existing_df = pd.DataFrame(
        {"value": [420000.0], "surprise": [float("nan")]},
        index=pd.to_datetime(["2024-01-05"]).tz_localize("UTC"),
    )

    captured_params: list[dict] = []

    def mock_get(url, params=None, timeout=None):
        captured_params.append(dict(params or {}))
        rows = _make_rows(["2024-01-12"], [422000.0])
        return _make_eia_response("WCRSTUS1", rows)

    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df

    with (
        patch("data.collectors.eia.requests.get", side_effect=mock_get),
        patch("data.collectors.eia.get_store", return_value=mock_store),
        patch("data.collectors.eia.get_settings") as mock_settings,
    ):
        mock_settings.return_value.eia_api_key = "test-key"
        mock_settings.return_value.eia_series = ["WCRSTUS1"]
        collect()

    assert len(captured_params) == 1
    assert captured_params[0].get("start") == "2024-01-06"


def test_collect_skips_empty_response():
    """If EIA returns empty data, write_series is not called."""

    def mock_get(url, params=None, timeout=None):
        return _make_eia_response("WCRSTUS1", [])

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.eia.requests.get", side_effect=mock_get),
        patch("data.collectors.eia.get_store", return_value=mock_store),
        patch("data.collectors.eia.get_settings") as mock_settings,
    ):
        mock_settings.return_value.eia_api_key = "test-key"
        mock_settings.return_value.eia_series = ["WCRSTUS1"]
        collect()

    mock_store.write_series.assert_not_called()


# ---------------------------------------------------------------------------
# DEFAULT_SERIES coverage
# ---------------------------------------------------------------------------


def test_default_series_has_four_expected_ids():
    expected = {"WCRSTUS1", "WCSSTUS1", "WGTSTUS1", "WDISTUS1"}
    assert set(DEFAULT_SERIES) == expected
