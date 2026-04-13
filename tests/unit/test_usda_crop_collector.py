# mypy: ignore-errors
"""
Unit tests for the USDA NASS crop progress collector.
All requests.get calls and store writes are mocked — no live API calls in tests.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.usda_crop import (
    _SERIES_MAP,
    DEFAULT_SERIES,
    _fetch_series,
    collect,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_nass_response(rows: list[dict]) -> MagicMock:
    """Build a mock requests.Response for NASS Quick Stats API data."""
    payload = {"data": rows}
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_rows(dates: list[str], values: list[str]) -> list[dict]:
    return [{"week_ending": d, "Value": v} for d, v in zip(dates, values)]


# ---------------------------------------------------------------------------
# Series map / DEFAULT_SERIES structure
# ---------------------------------------------------------------------------


def test_default_series_contains_corn_planted_natl():
    assert "USDA_CORN_PLANTED_NATL" in DEFAULT_SERIES


def test_default_series_contains_soybeans_planted_natl():
    assert "USDA_SOYBEANS_PLANTED_NATL" in DEFAULT_SERIES


def test_default_series_contains_state_level_series():
    # At least one state series for corn and soybeans
    corn_states = [
        k for k in DEFAULT_SERIES if k.startswith("USDA_CORN_") and not k.endswith("_NATL")
    ]
    soy_states = [
        k for k in DEFAULT_SERIES if k.startswith("USDA_SOYBEANS_") and not k.endswith("_NATL")
    ]
    assert len(corn_states) > 0
    assert len(soy_states) > 0


def test_series_map_covers_all_default_series():
    for key in DEFAULT_SERIES:
        assert key in _SERIES_MAP, f"{key} missing from _SERIES_MAP"


def test_series_map_corn_planted_natl_has_no_state():
    commodity, unit_desc, state_alpha = _SERIES_MAP["USDA_CORN_PLANTED_NATL"]
    assert commodity == "CORN"
    assert unit_desc == "PCT PLANTED"
    assert state_alpha is None


def test_series_map_soybeans_planted_il_has_state():
    commodity, unit_desc, state_alpha = _SERIES_MAP["USDA_SOYBEANS_PLANTED_IL"]
    assert commodity == "SOYBEANS"
    assert state_alpha == "IL"


# ---------------------------------------------------------------------------
# _fetch_series
# ---------------------------------------------------------------------------


def test_fetch_series_returns_pct_column():
    rows = _make_rows(["2024-05-06", "2024-05-13"], ["45", "62"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    assert "pct" in df.columns
    assert len(df) == 2


def test_fetch_series_index_is_utc_datetime():
    rows = _make_rows(["2024-05-06", "2024-05-13"], ["45", "62"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_fetch_series_empty_response_returns_empty_df():
    """Off-season: NASS returns empty data → empty DataFrame with pct column."""
    mock_resp = _make_nass_response([])

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    assert df.empty
    assert "pct" in df.columns


def test_fetch_series_sorted_ascending():
    rows = _make_rows(["2024-05-13", "2024-05-06"], ["62", "45"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    assert df.index[0] < df.index[1]


def test_fetch_series_drops_suppressed_values():
    """NASS uses '(D)' for suppressed/withheld data — should be dropped."""
    rows = [
        {"week_ending": "2024-05-06", "Value": "(D)"},
        {"week_ending": "2024-05-13", "Value": "62"},
    ]
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp):
        df = _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    assert len(df) == 1
    assert df["pct"].iloc[0] == pytest.approx(62.0)


def test_fetch_series_passes_api_key_in_params():
    rows = _make_rows(["2024-05-06"], ["45"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("my-usda-key", "USDA_CORN_PLANTED_NATL", None)

    call_params = mock_get.call_args[1]["params"]
    assert call_params.get("key") == "my-usda-key"


def test_fetch_series_omits_state_for_national():
    rows = _make_rows(["2024-05-06"], ["45"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", None)

    call_params = mock_get.call_args[1]["params"]
    assert "state_alpha" not in call_params


def test_fetch_series_includes_state_for_state_series():
    rows = _make_rows(["2024-05-06"], ["45"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "USDA_CORN_PLANTED_IL", None)

    call_params = mock_get.call_args[1]["params"]
    assert call_params.get("state_alpha") == "IL"


def test_fetch_series_passes_start_year_when_incremental():
    rows = _make_rows(["2024-05-06"], ["45"])
    mock_resp = _make_nass_response(rows)

    with patch("data.collectors.usda_crop.requests.get", return_value=mock_resp) as mock_get:
        _fetch_series("fake-key", "USDA_CORN_PLANTED_NATL", 2024)

    call_params = mock_get.call_args[1]["params"]
    assert call_params.get("year__GE") == "2024"


# ---------------------------------------------------------------------------
# collect — with mocked requests + store
# ---------------------------------------------------------------------------


def test_collect_writes_national_corn_and_soybean_planted():
    """collect() writes USDA_CORN_PLANTED_NATL and USDA_SOYBEANS_PLANTED_NATL."""
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    def mock_get(url, params=None, timeout=None):
        rows = _make_rows(["2024-05-06", "2024-05-13"], ["45", "62"])
        return _make_nass_response(rows)

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.usda_crop.requests.get", side_effect=mock_get),
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_CORN_PLANTED_NATL", "USDA_SOYBEANS_PLANTED_NATL"])

    assert "USDA_CORN_PLANTED_NATL" in written
    assert "USDA_SOYBEANS_PLANTED_NATL" in written

    for key in ["USDA_CORN_PLANTED_NATL", "USDA_SOYBEANS_PLANTED_NATL"]:
        df = written[key]
        assert "pct" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_collect_writes_state_series():
    """collect() writes at least one state series."""
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    def mock_get(url, params=None, timeout=None):
        rows = _make_rows(["2024-05-06"], ["45"])
        return _make_nass_response(rows)

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.usda_crop.requests.get", side_effect=mock_get),
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_CORN_PLANTED_IL", "USDA_SOYBEANS_PLANTED_IA"])

    assert "USDA_CORN_PLANTED_IL" in written
    assert "USDA_SOYBEANS_PLANTED_IA" in written


def test_collect_skips_empty_off_season_response():
    """Off-season: NASS returns empty → write_series not called, no exception."""

    def mock_get(url, params=None, timeout=None):
        return _make_nass_response([])

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.usda_crop.requests.get", side_effect=mock_get),
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_CORN_PLANTED_NATL"])  # no exception expected

    mock_store.write_series.assert_not_called()


def test_collect_idempotent_no_duplicate_rows():
    """Incremental: existing data through 2024-05-06, fetch returns both old and new row."""
    existing_df = pd.DataFrame(
        {"pct": [45.0]},
        index=pd.to_datetime(["2024-05-06"]).tz_localize("UTC"),
    )
    # API returns old + new row; collect should only write the new row
    rows = _make_rows(["2024-05-06", "2024-05-13"], ["45", "62"])

    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    # First read_series call (for incremental check) returns existing
    mock_store.read_series.return_value = existing_df
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.usda_crop.requests.get", return_value=_make_nass_response(rows)),
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_CORN_PLANTED_NATL"])

    assert "USDA_CORN_PLANTED_NATL" in written
    df = written["USDA_CORN_PLANTED_NATL"]
    assert len(df) == 1
    assert df["pct"].iloc[0] == pytest.approx(62.0)


def test_collect_skips_unknown_series_key():
    """collect() logs warning and skips unknown arc_key without crashing."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.usda_crop.requests.get") as mock_get,
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_UNKNOWN_KEY"])

    mock_get.assert_not_called()
    mock_store.write_series.assert_not_called()


def test_collect_writes_to_macro_library():
    """All writes go to the 'macro' ArcticDB library."""
    written_libs: list[str] = []

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written_libs.append(lib)

    def mock_get(url, params=None, timeout=None):
        rows = _make_rows(["2024-05-06"], ["45"])
        return _make_nass_response(rows)

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.usda_crop.requests.get", side_effect=mock_get),
        patch("data.collectors.usda_crop.get_store", return_value=mock_store),
        patch("data.collectors.usda_crop.get_settings") as mock_settings,
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        collect(series=["USDA_CORN_PLANTED_NATL", "USDA_SOYBEANS_PLANTED_NATL"])

    assert all(lib == "macro" for lib in written_libs)
