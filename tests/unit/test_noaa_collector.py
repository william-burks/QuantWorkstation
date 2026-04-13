# mypy: ignore-errors
"""
Unit tests for the NOAA Climate Data Online degree-day collector.
All requests.get calls and store writes are mocked — no live API calls in tests.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.noaa import (
    DEFAULT_SERIES,
    _SERIES_MAP,
    _fetch_series,
    collect,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_noaa_response(rows: list[dict]) -> MagicMock:
    """Build a mock requests.Response for NOAA CDO API data."""
    payload = {"results": rows}
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_rows(dates: list[str], values: list[float]) -> list[dict]:
    return [{"date": d, "value": v} for d, v in zip(dates, values)]


# ---------------------------------------------------------------------------
# _SERIES_MAP / DEFAULT_SERIES
# ---------------------------------------------------------------------------


def test_default_series_has_four_expected_keys():
    expected = {"NOAA_HDD_NATIONAL", "NOAA_CDD_NATIONAL", "NOAA_HDD_NORTHEAST", "NOAA_HDD_MIDWEST"}
    assert set(DEFAULT_SERIES) == expected


def test_series_map_covers_all_default_series():
    for key in DEFAULT_SERIES:
        assert key in _SERIES_MAP, f"{key} missing from _SERIES_MAP"


def test_series_map_datatypes():
    assert _SERIES_MAP["NOAA_HDD_NATIONAL"][0] == "HDD"
    assert _SERIES_MAP["NOAA_CDD_NATIONAL"][0] == "CDD"
    assert _SERIES_MAP["NOAA_HDD_NORTHEAST"][0] == "HDD"
    assert _SERIES_MAP["NOAA_HDD_MIDWEST"][0] == "HDD"


def test_series_map_locationids():
    assert _SERIES_MAP["NOAA_HDD_NATIONAL"][1] == "CLIM:US"
    assert _SERIES_MAP["NOAA_CDD_NATIONAL"][1] == "CLIM:US"
    assert _SERIES_MAP["NOAA_HDD_NORTHEAST"][1] == "CLIM:R1"
    assert _SERIES_MAP["NOAA_HDD_MIDWEST"][1] == "CLIM:R4"


# ---------------------------------------------------------------------------
# _fetch_series
# ---------------------------------------------------------------------------


def test_fetch_series_returns_value_column():
    rows = _make_rows(["2024-01-05", "2024-01-12"], [120.0, 135.0])
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "NOAA_HDD_NATIONAL", None)

    assert "value" in df.columns
    assert len(df) == 2


def test_fetch_series_index_is_utc_datetime():
    rows = _make_rows(["2024-01-05", "2024-01-12"], [120.0, 135.0])
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "NOAA_HDD_NATIONAL", None)

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_fetch_series_empty_response_returns_empty_df():
    mock_resp = _make_noaa_response([])

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "NOAA_HDD_NATIONAL", None)

    assert df.empty
    assert "value" in df.columns


def test_fetch_series_sorted_ascending():
    rows = _make_rows(["2024-01-12", "2024-01-05"], [135.0, 120.0])
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "NOAA_HDD_NATIONAL", None)

    assert df.index[0] < df.index[1]


def test_fetch_series_passes_startdate_when_incremental():
    rows = _make_rows(["2024-06-07"], [5.0])
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "NOAA_CDD_NATIONAL", "2024-06-07")

    call_params = mock_get.call_args[1]["params"]
    assert call_params.get("startdate") == "2024-06-07"


def test_fetch_series_token_header_sent():
    rows = _make_rows(["2024-01-05"], [100.0])
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("my-api-key", "NOAA_HDD_NATIONAL", None)

    headers = mock_get.call_args[1]["headers"]
    assert headers.get("token") == "my-api-key"


def test_fetch_series_drops_null_values():
    rows = [{"date": "2024-01-05", "value": None}, {"date": "2024-01-12", "value": 100.0}]
    mock_resp = _make_noaa_response(rows)

    with patch("data.collectors.noaa.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "NOAA_HDD_NATIONAL", None)

    assert len(df) == 1
    assert df["value"].iloc[0] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# collect — with mocked requests + store
# ---------------------------------------------------------------------------


def test_collect_writes_all_four_series():
    """collect() calls store.write_series() once per default series."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    def mock_get(url, params=None, headers=None, timeout=None):
        rows = _make_rows(["2024-01-05", "2024-01-12"], [120.0, 135.0])
        return _make_noaa_response(rows)

    with (
        patch("data.collectors.noaa.requests.get", side_effect=mock_get),
        patch("data.collectors.noaa.get_store", return_value=mock_store),
        patch("data.collectors.noaa.get_settings") as mock_settings,
    ):
        mock_settings.return_value.noaa_api_key = "test-key"
        mock_settings.return_value.noaa_series = list(DEFAULT_SERIES)
        collect()

    calls = mock_store.write_series.call_args_list
    assert len(calls) == 4

    keys_written = {c[0][1] for c in calls}
    assert keys_written == set(DEFAULT_SERIES)

    libs = {c[0][0] for c in calls}
    assert libs == {"macro"}


def test_collect_written_df_has_value_column_and_datetime_index():
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    def mock_get(url, params=None, headers=None, timeout=None):
        rows = _make_rows(["2024-01-05", "2024-01-12"], [120.0, 135.0])
        return _make_noaa_response(rows)

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.noaa.requests.get", side_effect=mock_get),
        patch("data.collectors.noaa.get_store", return_value=mock_store),
        patch("data.collectors.noaa.get_settings") as mock_settings,
    ):
        mock_settings.return_value.noaa_api_key = "test-key"
        mock_settings.return_value.noaa_series = ["NOAA_HDD_NATIONAL"]
        collect()

    assert "NOAA_HDD_NATIONAL" in written
    df = written["NOAA_HDD_NATIONAL"]
    assert "value" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_collect_incremental_passes_start_date():
    """If existing data present, collect uses last date + 1 day as startdate."""
    existing_df = pd.DataFrame(
        {"value": [120.0]},
        index=pd.to_datetime(["2024-01-05"]).tz_localize("UTC"),
    )

    captured_params: list[dict] = []

    def mock_get(url, params=None, headers=None, timeout=None):
        captured_params.append(dict(params or {}))
        rows = _make_rows(["2024-01-12"], [135.0])
        return _make_noaa_response(rows)

    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df

    with (
        patch("data.collectors.noaa.requests.get", side_effect=mock_get),
        patch("data.collectors.noaa.get_store", return_value=mock_store),
        patch("data.collectors.noaa.get_settings") as mock_settings,
    ):
        mock_settings.return_value.noaa_api_key = "test-key"
        mock_settings.return_value.noaa_series = ["NOAA_HDD_NATIONAL"]
        collect()

    assert len(captured_params) == 1
    assert captured_params[0].get("startdate") == "2024-01-06"


def test_collect_skips_empty_response():
    """If NOAA returns empty results, write_series is not called."""

    def mock_get(url, params=None, headers=None, timeout=None):
        return _make_noaa_response([])

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.noaa.requests.get", side_effect=mock_get),
        patch("data.collectors.noaa.get_store", return_value=mock_store),
        patch("data.collectors.noaa.get_settings") as mock_settings,
    ):
        mock_settings.return_value.noaa_api_key = "test-key"
        mock_settings.return_value.noaa_series = ["NOAA_HDD_NATIONAL"]
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_skips_unknown_series_key():
    """collect() logs warning and skips unknown arc_key without crashing."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.noaa.requests.get") as mock_get,
        patch("data.collectors.noaa.get_store", return_value=mock_store),
        patch("data.collectors.noaa.get_settings") as mock_settings,
    ):
        mock_settings.return_value.noaa_api_key = "test-key"
        mock_settings.return_value.noaa_series = ["NOAA_UNKNOWN_KEY"]
        collect()

    mock_get.assert_not_called()
    mock_store.write_series.assert_not_called()
