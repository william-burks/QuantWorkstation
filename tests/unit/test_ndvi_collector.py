# mypy: ignore-errors
"""
Unit tests for the NASA AppEEARS NDVI crop health collector.
All HTTP calls and store writes are mocked — no live API calls.
"""

from datetime import UTC, date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.ndvi import (
    REGION_BBOX,
    REGIONS,
    _build_task_payload,
    _compute_anomaly,
    _compute_climatology,
    _download_bundle_csv,
    _get_bearer_token,
    _is_off_season,
    _poll_task,
    _submit_task,
    collect,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bearer_resp(token: str = "test-bearer-token") -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"token": token}
    mock.raise_for_status.return_value = None
    return mock


def _make_submit_resp(task_id: str = "abc123") -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"task_id": task_id}
    mock.raise_for_status.return_value = None
    return mock


def _make_status_resp(status: str) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"status": status}
    mock.raise_for_status.return_value = None
    return mock


def _make_bundle_list_resp(file_id: str = "file001", file_name: str = "output.csv") -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"files": [{"file_id": file_id, "file_name": file_name}]}
    mock.raise_for_status.return_value = None
    return mock


def _make_csv_download_resp(csv_content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = csv_content.encode("utf-8")
    mock.raise_for_status.return_value = None
    return mock


def _sample_ndvi_csv() -> str:
    """CSV matching AppEEARS output format with NDVI column."""
    return (
        "Date,MOD13Q1_061__250m_16_days_NDVI\n2024-05-01,5500\n2024-05-17,6200\n2024-06-02,7100\n"
    )


def _sample_ndvi_df() -> pd.DataFrame:
    """Pre-built ndvi DataFrame matching _sample_ndvi_csv after parsing."""
    dates = pd.to_datetime(["2024-05-01", "2024-05-17", "2024-06-02"], utc=True)
    return pd.DataFrame({"ndvi": [0.55, 0.62, 0.71]}, index=dates)


def _sample_clim_df() -> pd.DataFrame:
    """Minimal climatology DataFrame (day-of-year indexed)."""
    doy = [122, 138, 154]  # approx doy for May 1, May 17, Jun 2
    return pd.DataFrame({"ndvi_mean": [0.50, 0.60, 0.68]}, index=doy)


# ---------------------------------------------------------------------------
# _is_off_season
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("month", [11, 12, 1, 2, 3])
def test_is_off_season_returns_true_for_off_months(month):
    d = date(2024, month, 15)
    assert _is_off_season(d) is True


@pytest.mark.parametrize("month", [4, 5, 6, 7, 8, 9, 10])
def test_is_off_season_returns_false_for_growing_months(month):
    d = date(2024, month, 15)
    assert _is_off_season(d) is False


# ---------------------------------------------------------------------------
# REGION_BBOX / REGIONS constants
# ---------------------------------------------------------------------------


def test_all_regions_present():
    expected = {"CORN_BELT", "IOWA", "ILLINOIS", "INDIANA", "NEBRASKA", "MINNESOTA"}
    assert set(REGIONS) == expected


def test_all_region_bboxes_have_four_coords():
    for region, bbox in REGION_BBOX.items():
        assert len(bbox) == 4, f"{region} bbox should have 4 coords"


# ---------------------------------------------------------------------------
# _get_bearer_token
# ---------------------------------------------------------------------------


def test_get_bearer_token_posts_to_login_endpoint():
    mock_resp = _make_bearer_resp("my-bearer")
    with patch("data.collectors.ndvi.requests.post", return_value=mock_resp) as mock_post:
        token = _get_bearer_token("earthdata-token-123")

    assert token == "my-bearer"
    call_url = mock_post.call_args[0][0]
    assert "login" in call_url


def test_get_bearer_token_sends_bearer_header():
    mock_resp = _make_bearer_resp()
    with patch("data.collectors.ndvi.requests.post", return_value=mock_resp) as mock_post:
        _get_bearer_token("earthdata-xyz")

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer earthdata-xyz"


# ---------------------------------------------------------------------------
# _build_task_payload
# ---------------------------------------------------------------------------


def test_build_task_payload_contains_region_and_dates():
    payload = _build_task_payload("IOWA", "2024-05-01", "2024-08-31", "test_task")
    assert payload["task_name"] == "test_task"
    assert payload["task_type"] == "area"
    dates = payload["params"]["dates"]
    assert dates[0]["startDate"] == "2024-05-01"
    assert dates[0]["endDate"] == "2024-08-31"


def test_build_task_payload_uses_modis_product():
    payload = _build_task_payload("IOWA", "2024-05-01", "2024-08-31", "test_task")
    layers = payload["params"]["layers"]
    assert any("MOD13Q1" in layer["product"] for layer in layers)


def test_build_task_payload_csv_output():
    payload = _build_task_payload("IOWA", "2024-05-01", "2024-08-31", "test_task")
    fmt = payload["params"]["output"]["format"]["type"]
    assert fmt == "csv"


# ---------------------------------------------------------------------------
# _submit_task
# ---------------------------------------------------------------------------


def test_submit_task_returns_task_id():
    mock_resp = _make_submit_resp("task-id-001")
    with patch("data.collectors.ndvi.requests.post", return_value=mock_resp):
        task_id = _submit_task("bearer-tok", {"task_type": "area"})
    assert task_id == "task-id-001"


def test_submit_task_sends_bearer_header():
    mock_resp = _make_submit_resp()
    with patch("data.collectors.ndvi.requests.post", return_value=mock_resp) as mock_post:
        _submit_task("my-bearer", {})
    headers = mock_post.call_args[1]["headers"]
    assert "Bearer my-bearer" in headers["Authorization"]


# ---------------------------------------------------------------------------
# _poll_task
# ---------------------------------------------------------------------------


def test_poll_task_returns_done_on_first_hit():
    mock_resp = _make_status_resp("done")
    with patch("data.collectors.ndvi.requests.get", return_value=mock_resp):
        with patch("data.collectors.ndvi.time.sleep"):
            status = _poll_task("bearer", "task-xyz")
    assert status == "done"


def test_poll_task_waits_then_returns_done():
    responses = [_make_status_resp("processing"), _make_status_resp("done")]
    with patch("data.collectors.ndvi.requests.get", side_effect=responses):
        with patch("data.collectors.ndvi.time.sleep"):
            status = _poll_task("bearer", "task-xyz")
    assert status == "done"


def test_poll_task_returns_error_status():
    mock_resp = _make_status_resp("error")
    with patch("data.collectors.ndvi.requests.get", return_value=mock_resp):
        with patch("data.collectors.ndvi.time.sleep"):
            status = _poll_task("bearer", "task-xyz")
    assert status == "error"


def test_poll_task_raises_timeout():
    mock_resp = _make_status_resp("processing")
    with patch("data.collectors.ndvi.requests.get", return_value=mock_resp):
        with patch("data.collectors.ndvi.time.sleep"):
            with patch("data.collectors.ndvi.POLL_MAX_ATTEMPTS", 2):
                with pytest.raises(TimeoutError):
                    _poll_task("bearer", "task-xyz")


# ---------------------------------------------------------------------------
# _download_bundle_csv
# ---------------------------------------------------------------------------


def test_download_bundle_csv_returns_ndvi_column():
    bundle_resp = _make_bundle_list_resp()
    csv_resp = _make_csv_download_resp(_sample_ndvi_csv())

    with patch("data.collectors.ndvi.requests.get", side_effect=[bundle_resp, csv_resp]):
        df = _download_bundle_csv("bearer", "task-abc")

    assert "ndvi" in df.columns
    assert len(df) == 3


def test_download_bundle_csv_index_is_utc_datetime():
    bundle_resp = _make_bundle_list_resp()
    csv_resp = _make_csv_download_resp(_sample_ndvi_csv())

    with patch("data.collectors.ndvi.requests.get", side_effect=[bundle_resp, csv_resp]):
        df = _download_bundle_csv("bearer", "task-abc")

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_download_bundle_csv_scales_ndvi_to_zero_one():
    """MODIS raw values (e.g. 5500) scaled by 0.0001 → 0.55."""
    bundle_resp = _make_bundle_list_resp()
    csv_resp = _make_csv_download_resp(_sample_ndvi_csv())

    with patch("data.collectors.ndvi.requests.get", side_effect=[bundle_resp, csv_resp]):
        df = _download_bundle_csv("bearer", "task-abc")

    assert df["ndvi"].between(0.0, 1.0).all()


def test_download_bundle_csv_empty_when_no_csv_files():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"files": []}
    mock_resp.raise_for_status.return_value = None

    with patch("data.collectors.ndvi.requests.get", return_value=mock_resp):
        df = _download_bundle_csv("bearer", "task-abc")

    assert df.empty
    assert "ndvi" in df.columns


# ---------------------------------------------------------------------------
# _compute_climatology
# ---------------------------------------------------------------------------


def test_compute_climatology_indexed_by_doy():
    df = _sample_ndvi_df()
    clim = _compute_climatology(df)
    # All index values should be day-of-year (1–366)
    assert clim.index.min() >= 1
    assert clim.index.max() <= 366


def test_compute_climatology_has_ndvi_mean_column():
    df = _sample_ndvi_df()
    clim = _compute_climatology(df)
    assert "ndvi_mean" in clim.columns


def test_compute_climatology_mean_values_in_range():
    df = _sample_ndvi_df()
    clim = _compute_climatology(df)
    assert clim["ndvi_mean"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# _compute_anomaly
# ---------------------------------------------------------------------------


def test_compute_anomaly_adds_anomaly_column():
    df = _sample_ndvi_df()
    clim = _compute_climatology(df)
    result = _compute_anomaly(df, clim)
    assert "ndvi_anomaly" in result.columns
    assert "ndvi" in result.columns


def test_compute_anomaly_zero_when_ndvi_equals_clim():
    dates = pd.to_datetime(["2024-05-01"], utc=True)
    df = pd.DataFrame({"ndvi": [0.60]}, index=dates)
    doy = 122  # approx doy for May 1
    clim = pd.DataFrame({"ndvi_mean": [0.60]}, index=[doy])
    result = _compute_anomaly(df, clim)
    assert abs(result["ndvi_anomaly"].iloc[0]) < 1e-9


def test_compute_anomaly_positive_when_ndvi_above_clim():
    dates = pd.to_datetime(["2024-05-01"], utc=True)
    df = pd.DataFrame({"ndvi": [0.70]}, index=dates)
    doy = 122
    clim = pd.DataFrame({"ndvi_mean": [0.60]}, index=[doy])
    result = _compute_anomaly(df, clim)
    assert result["ndvi_anomaly"].iloc[0] > 0


def test_compute_anomaly_negative_when_ndvi_below_clim():
    dates = pd.to_datetime(["2024-05-01"], utc=True)
    df = pd.DataFrame({"ndvi": [0.40]}, index=dates)
    doy = 122
    clim = pd.DataFrame({"ndvi_mean": [0.60]}, index=[doy])
    result = _compute_anomaly(df, clim)
    assert result["ndvi_anomaly"].iloc[0] < 0


# ---------------------------------------------------------------------------
# collect — off-season guard
# ---------------------------------------------------------------------------


def test_collect_no_op_in_off_season():
    """collect() in Nov–Mar must not call any HTTP or store."""
    with (
        patch("data.collectors.ndvi._is_off_season", return_value=True),
        patch("data.collectors.ndvi.requests.post") as mock_post,
        patch("data.collectors.ndvi.requests.get") as mock_get,
        patch("data.collectors.ndvi.get_store") as mock_store_fn,
    ):
        collect()

    mock_post.assert_not_called()
    mock_get.assert_not_called()
    mock_store_fn.assert_not_called()


# ---------------------------------------------------------------------------
# collect — full integration (mocked)
# ---------------------------------------------------------------------------


def _make_appeears_http_sequence(csv_content: str):
    """Build the ordered HTTP responses collect() makes for a single region."""
    login_resp = _make_bearer_resp()
    submit_resp = _make_submit_resp("task-001")
    status_resp = _make_status_resp("done")
    bundle_list_resp = _make_bundle_list_resp()
    csv_download_resp = _make_csv_download_resp(csv_content)
    return [login_resp, submit_resp, status_resp, bundle_list_resp, csv_download_resp]


def test_collect_writes_ndvi_and_anomaly_columns_for_single_region():
    written: dict[str, pd.DataFrame] = {}

    def capture(lib, sym, df):
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    responses = _make_appeears_http_sequence(_sample_ndvi_csv())

    with (
        patch("data.collectors.ndvi._is_off_season", return_value=False),
        patch("data.collectors.ndvi.requests.post", side_effect=[responses[0], responses[1]]),
        patch("data.collectors.ndvi.requests.get", side_effect=responses[2:]),
        patch("data.collectors.ndvi.time.sleep"),
        patch("data.collectors.ndvi.get_store", return_value=mock_store),
        patch("data.collectors.ndvi.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasa_earthdata_token = "test-token"
        collect(regions=["IOWA"])

    assert "NDVI_IOWA_1D" in written
    df = written["NDVI_IOWA_1D"]
    assert "ndvi" in df.columns
    assert "ndvi_anomaly" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_collect_writes_climatology_series():
    written: dict[str, pd.DataFrame] = {}

    def capture(lib, sym, df):
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    responses = _make_appeears_http_sequence(_sample_ndvi_csv())

    with (
        patch("data.collectors.ndvi._is_off_season", return_value=False),
        patch("data.collectors.ndvi.requests.post", side_effect=[responses[0], responses[1]]),
        patch("data.collectors.ndvi.requests.get", side_effect=responses[2:]),
        patch("data.collectors.ndvi.time.sleep"),
        patch("data.collectors.ndvi.get_store", return_value=mock_store),
        patch("data.collectors.ndvi.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasa_earthdata_token = "test-token"
        collect(regions=["IOWA"])

    assert "NDVI_IOWA_CLIM_1D" in written
    clim = written["NDVI_IOWA_CLIM_1D"]
    assert "ndvi_mean" in clim.columns


def test_collect_skips_unknown_region():
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.ndvi._is_off_season", return_value=False),
        patch("data.collectors.ndvi.requests.post") as mock_post,
        patch("data.collectors.ndvi.get_store", return_value=mock_store),
        patch("data.collectors.ndvi.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasa_earthdata_token = "test-token"
        # Login POST should still happen for bearer token
        mock_post.return_value = _make_bearer_resp()
        collect(regions=["UNKNOWN_REGION"])

    mock_store.write_series.assert_not_called()


def test_collect_idempotent_no_duplicate_rows():
    """If last stored date equals data date, no rows written after dedup."""
    existing_df = pd.DataFrame(
        {"ndvi": [0.55], "ndvi_anomaly": [0.05]},
        index=pd.to_datetime(["2024-05-01"]).tz_localize("UTC"),
    )

    # The "new" data only has 2024-05-01 which is already stored
    csv_with_same_date = "Date,MOD13Q1_061__250m_16_days_NDVI\n2024-05-01,5500\n"

    written_keys: list[str] = []

    def capture(lib, sym, df):
        written_keys.append(sym)

    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df
    mock_store.write_series.side_effect = capture

    responses = _make_appeears_http_sequence(csv_with_same_date)

    with (
        patch("data.collectors.ndvi._is_off_season", return_value=False),
        patch("data.collectors.ndvi.requests.post", side_effect=[responses[0], responses[1]]),
        patch("data.collectors.ndvi.requests.get", side_effect=responses[2:]),
        patch("data.collectors.ndvi.time.sleep"),
        patch("data.collectors.ndvi.get_store", return_value=mock_store),
        patch("data.collectors.ndvi.get_settings") as mock_settings,
    ):
        mock_settings.return_value.nasa_earthdata_token = "test-token"
        collect(regions=["IOWA"])

    # Climatology write happens; data write should not (all dupes)
    assert "NDVI_IOWA_1D" not in written_keys
