# mypy: ignore-errors
"""
Unit tests for the BDTI (Baltic Dirty Tanker Index) collector.
All requests.get calls and store writes are mocked — no live API calls in tests.
"""

from datetime import timezone
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from data.collectors.bdti import ARC_KEY, NDQL_DATASET, _fetch_bdti, collect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_response(data: list[list], status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response with a Nasdaq Data Link-shaped payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "dataset": {
            "data": data,
        }
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _sample_data() -> list[list]:
    return [
        ["2024-01-02", 750.0],
        ["2024-01-03", 760.0],
        ["2024-01-04", 755.0],
    ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_arc_key_value():
    assert ARC_KEY == "BDTI_1D"


def test_dataset_code():
    assert NDQL_DATASET == "BWAVE/BDTI"


# ---------------------------------------------------------------------------
# _fetch_bdti
# ---------------------------------------------------------------------------


def test_fetch_bdti_returns_value_column():
    mock_resp = _make_response(_sample_data())
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        df = _fetch_bdti("test-key", None)

    assert list(df.columns) == ["value"]
    assert len(df) == 3


def test_fetch_bdti_index_is_utc_datetime():
    mock_resp = _make_response(_sample_data())
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        df = _fetch_bdti("test-key", None)

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == timezone.utc


def test_fetch_bdti_sorted_ascending():
    # Reverse order input — output should be sorted asc
    data = [["2024-01-04", 755.0], ["2024-01-02", 750.0], ["2024-01-03", 760.0]]
    mock_resp = _make_response(data)
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        df = _fetch_bdti("test-key", None)

    assert list(df.index) == sorted(df.index)


def test_fetch_bdti_passes_start_date_param():
    mock_resp = _make_response(_sample_data())
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp) as mock_get:
        _fetch_bdti("test-key", "2024-01-03")

    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["start_date"] == "2024-01-03"


def test_fetch_bdti_no_start_date_when_none():
    mock_resp = _make_response(_sample_data())
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp) as mock_get:
        _fetch_bdti("test-key", None)

    call_kwargs = mock_get.call_args[1]
    assert "start_date" not in call_kwargs["params"]


def test_fetch_bdti_empty_data_returns_empty_df():
    mock_resp = _make_response([])
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        df = _fetch_bdti("test-key", None)

    assert df.empty
    assert "value" in df.columns


def test_fetch_bdti_drops_nan_rows():
    data = [["2024-01-02", None], ["2024-01-03", 760.0]]
    mock_resp = _make_response(data)
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        df = _fetch_bdti("test-key", None)

    assert len(df) == 1
    assert not df["value"].isna().any()


def test_fetch_bdti_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
    with patch("data.collectors.bdti.requests.get", return_value=mock_resp):
        with pytest.raises(Exception, match="404"):
            _fetch_bdti("test-key", None)


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def test_collect_writes_bdti_1d_to_macro():
    mock_resp = _make_response(_sample_data())
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.bdti.requests.get", return_value=mock_resp),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
        patch("data.collectors.bdti.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasdaq_data_link_api_key = "test-key"
        collect()

    mock_store.write_series.assert_called_once()
    args = mock_store.write_series.call_args[0]
    assert args[0] == "macro"
    assert args[1] == "BDTI_1D"


def test_collect_written_df_has_value_column_and_datetime_index():
    mock_resp = _make_response(_sample_data())
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.bdti.requests.get", return_value=mock_resp),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
        patch("data.collectors.bdti.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasdaq_data_link_api_key = "test-key"
        collect()

    assert "BDTI_1D" in written
    df = written["BDTI_1D"]
    assert list(df.columns) == ["value"]
    assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_collect_incremental_uses_last_date_plus_one():
    existing_df = pd.DataFrame(
        {"value": [750.0]},
        index=pd.to_datetime(["2024-01-03"]).tz_localize("UTC"),
    )
    mock_resp = _make_response([["2024-01-04", 755.0]])
    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df

    with (
        patch("data.collectors.bdti.requests.get", return_value=mock_resp) as mock_get,
        patch("data.collectors.bdti.get_store", return_value=mock_store),
        patch("data.collectors.bdti.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasdaq_data_link_api_key = "test-key"
        collect()

    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["start_date"] == "2024-01-04"


def test_collect_skips_write_when_no_new_data():
    mock_resp = _make_response([])
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.bdti.requests.get", return_value=mock_resp),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
        patch("data.collectors.bdti.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasdaq_data_link_api_key = "test-key"
        collect()

    mock_store.write_series.assert_not_called()
