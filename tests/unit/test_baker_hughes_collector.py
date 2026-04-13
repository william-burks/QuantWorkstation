# mypy: ignore-errors
"""
Unit tests for the Baker Hughes North America rig count collector.
All requests.get calls and store writes are mocked — no live HTTP calls.
"""

from datetime import UTC
from io import BytesIO
from unittest.mock import MagicMock, patch

import openpyxl
import pandas as pd
import pytest

from data.collectors.baker_hughes import (
    BHI_NA_EXCEL_URL,
    SERIES_KEYS,
    _download_excel,
    _parse_na_rig_count,
    collect,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_excel_bytes(
    rows: list[tuple],
    sheet_name: str = "North America Rig Count",
) -> bytes:
    """Build a minimal Baker Hughes-style Excel workbook as bytes.

    Args:
        rows: List of (date_str, us_total, us_oil, us_gas, canada) tuples.
        sheet_name: Sheet name to create.

    Returns:
        Raw .xlsx bytes.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    # Header row matching the column names the parser expects
    ws.append(
        [
            "Date",
            "United States Total",
            "United States Oil",
            "United States Gas",
            "Canada Total",
        ]
    )
    for date_str, us_total, us_oil, us_gas, canada in rows:
        ws.append([date_str, us_total, us_oil, us_gas, canada])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sample_rows() -> list[tuple]:
    return [
        ("2024-01-05", 600, 480, 110, 190),
        ("2024-01-12", 605, 485, 111, 192),
        ("2024-01-19", 598, 478, 109, 188),
    ]


# ---------------------------------------------------------------------------
# _download_excel
# ---------------------------------------------------------------------------


def test_download_excel_returns_bytes():
    mock_resp = MagicMock()
    mock_resp.content = b"fake-excel-bytes"
    mock_resp.raise_for_status.return_value = None

    with patch("data.collectors.baker_hughes.requests.get", return_value=mock_resp) as mock_get:
        result = _download_excel("https://example.com/rig.xlsx")

    assert result == b"fake-excel-bytes"
    mock_get.assert_called_once()


def test_download_excel_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 404")

    with patch("data.collectors.baker_hughes.requests.get", return_value=mock_resp):
        with pytest.raises(Exception, match="HTTP 404"):
            _download_excel("https://example.com/rig.xlsx")


# ---------------------------------------------------------------------------
# _parse_na_rig_count
# ---------------------------------------------------------------------------


def test_parse_returns_all_four_series():
    excel_bytes = _make_excel_bytes(_sample_rows())
    result = _parse_na_rig_count(excel_bytes)

    assert set(result.keys()) == {
        "BHI_US_TOTAL_RIGS",
        "BHI_US_OIL_RIGS",
        "BHI_US_GAS_RIGS",
        "BHI_CANADA_RIGS",
    }


def test_parse_count_column_present():
    excel_bytes = _make_excel_bytes(_sample_rows())
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert "count" in df.columns, f"{key} missing 'count' column"


def test_parse_index_is_utc_datetime():
    excel_bytes = _make_excel_bytes(_sample_rows())
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert pd.api.types.is_datetime64_any_dtype(df.index), f"{key} index not datetime"
        assert df.index.tz == UTC, f"{key} index not UTC"


def test_parse_correct_row_count():
    excel_bytes = _make_excel_bytes(_sample_rows())
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert len(df) == 3, f"{key} expected 3 rows, got {len(df)}"


def test_parse_correct_values():
    excel_bytes = _make_excel_bytes(_sample_rows())
    result = _parse_na_rig_count(excel_bytes)

    us_total = result["BHI_US_TOTAL_RIGS"]
    assert int(us_total["count"].iloc[0]) == 600
    assert int(us_total["count"].iloc[1]) == 605

    canada = result["BHI_CANADA_RIGS"]
    assert int(canada["count"].iloc[0]) == 190


def test_parse_sorted_ascending():
    # Reverse order in sheet
    rows = [
        ("2024-01-19", 598, 478, 109, 188),
        ("2024-01-05", 600, 480, 110, 190),
        ("2024-01-12", 605, 485, 111, 192),
    ]
    excel_bytes = _make_excel_bytes(rows)
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert df.index.is_monotonic_increasing, f"{key} index not sorted ascending"


def test_parse_drops_non_date_rows():
    """Non-date rows (notes, blank rows) should be silently dropped."""
    rows = [
        ("2024-01-05", 600, 480, 110, 190),
        ("NOT A DATE", 0, 0, 0, 0),  # should be dropped
        ("2024-01-12", 605, 485, 111, 192),
    ]
    excel_bytes = _make_excel_bytes(rows)
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert len(df) == 2, f"{key} expected 2 rows after dropping bad row, got {len(df)}"


def test_parse_raises_on_missing_sheet():
    excel_bytes = _make_excel_bytes(_sample_rows(), sheet_name="Wrong Sheet")
    with pytest.raises(Exception):
        _parse_na_rig_count(excel_bytes)


# ---------------------------------------------------------------------------
# collect — mocked HTTP + store
# ---------------------------------------------------------------------------


def _mock_requests_get(excel_bytes: bytes):
    """Return a mock requests.get that returns *excel_bytes*."""
    mock_resp = MagicMock()
    mock_resp.content = excel_bytes
    mock_resp.raise_for_status.return_value = None
    return MagicMock(return_value=mock_resp)


def test_collect_writes_all_four_series():
    """collect() calls store.write_series() once per series key."""
    excel_bytes = _make_excel_bytes(_sample_rows())
    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    calls = mock_store.write_series.call_args_list
    assert len(calls) == 4

    keys_written = {c[0][1] for c in calls}
    assert keys_written == set(SERIES_KEYS)

    libs = {c[0][0] for c in calls}
    assert libs == {"macro"}


def test_collect_written_df_has_count_column_and_datetime_index():
    """DataFrames written to store have 'count' column and UTC DatetimeIndex."""
    excel_bytes = _make_excel_bytes(_sample_rows())
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    for key in SERIES_KEYS:
        assert key in written
        df = written[key]
        assert "count" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df.index)
        assert df.index.tz == UTC


def test_collect_incremental_appends_only_new_rows():
    """If existing data present, collect appends only rows after last stored date."""
    excel_bytes = _make_excel_bytes(_sample_rows())

    existing_df = pd.DataFrame(
        {"count": pd.array([600], dtype="Int64")},
        index=pd.to_datetime(["2024-01-05"]).tz_localize("UTC"),
    )
    existing_df.index.name = "date"

    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df
    mock_store.write_series.side_effect = capture

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    # Each series should have only rows after 2024-01-05 (i.e. 2 rows)
    for key in SERIES_KEYS:
        assert key in written
        assert len(written[key]) == 2, f"{key}: expected 2 new rows, got {len(written[key])}"


def test_collect_idempotent_no_write_when_fully_up_to_date():
    """If last stored date is current, write_series is not called."""
    excel_bytes = _make_excel_bytes(_sample_rows())

    # Last stored date matches the most recent row in the fixture
    existing_df = pd.DataFrame(
        {"count": pd.array([598], dtype="Int64")},
        index=pd.to_datetime(["2024-01-19"]).tz_localize("UTC"),
    )
    existing_df.index.name = "date"

    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_skips_series_on_parse_empty():
    """collect() does not call write_series for any series with no parsed rows."""
    # Sheet with no data rows (only header)
    excel_bytes = _make_excel_bytes([])

    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_uses_default_url():
    """collect() fetches from BHI_NA_EXCEL_URL by default."""
    excel_bytes = _make_excel_bytes(_sample_rows())
    mock_get = _mock_requests_get(excel_bytes)
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.baker_hughes.requests.get", mock_get),
        patch("data.collectors.baker_hughes.get_store", return_value=mock_store),
    ):
        collect()

    call_url = mock_get.call_args[0][0]
    assert call_url == BHI_NA_EXCEL_URL


# ---------------------------------------------------------------------------
# SERIES_KEYS constant
# ---------------------------------------------------------------------------


def test_series_keys_has_four_expected_keys():
    expected = {
        "BHI_US_TOTAL_RIGS",
        "BHI_US_OIL_RIGS",
        "BHI_US_GAS_RIGS",
        "BHI_CANADA_RIGS",
    }
    assert set(SERIES_KEYS) == expected
