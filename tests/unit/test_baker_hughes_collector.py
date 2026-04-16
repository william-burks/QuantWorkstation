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
    date_str: str | None = "2024-01-05",
    us_total: int = 600,
    us_oil: int = 480,
    us_gas: int = 110,
    canada: int = 190,
    sheet_name: str = "North America Rig Count",
) -> bytes:
    """Build a minimal BHI-format Excel workbook as bytes (single-week snapshot).

    Mirrors the real BHI NA rig count sheet structure:
    - Row 3 (0-indexed): date value in col 3
    - Subsequent rows: label in col 1, this-week count in col 3

    Args:
        date_str: ISO date string for the report week. None → missing date (parse error).
        us_total: US total rig count.
        us_oil: US oil rig count.
        us_gas: US gas rig count.
        canada: Canada rig count.
        sheet_name: Sheet name to create.

    Returns:
        Raw .xlsx bytes.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    # Rows 0-2: junk/header rows (match real BHI layout; use non-None so openpyxl keeps them)
    for i in range(3):
        ws.append([f"row{i}", None, None, None, None])
    # Row 3: date in col 3 (0-indexed → openpyxl 1-indexed col 4)
    ws.append(["row3", None, None, date_str, None])

    # Label rows: col 1 = label, col 3 = value (0-indexed)
    if date_str is not None:
        ws.append([None, "United States Total", None, us_total, None])
        ws.append([None, "Oil", None, us_oil, None])
        ws.append([None, "Gas", None, us_gas, None])
        ws.append([None, "Canada", None, canada, None])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


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
    excel_bytes = _make_excel_bytes()
    result = _parse_na_rig_count(excel_bytes)

    assert set(result.keys()) == {
        "BHI_US_TOTAL_RIGS",
        "BHI_US_OIL_RIGS",
        "BHI_US_GAS_RIGS",
        "BHI_CANADA_RIGS",
    }


def test_parse_count_column_present():
    excel_bytes = _make_excel_bytes()
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert "count" in df.columns, f"{key} missing 'count' column"


def test_parse_index_is_utc_datetime():
    excel_bytes = _make_excel_bytes()
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert pd.api.types.is_datetime64_any_dtype(df.index), f"{key} index not datetime"
        assert df.index.tz == UTC, f"{key} index not UTC"


def test_parse_correct_row_count():
    """Parser returns one row per series (single weekly snapshot)."""
    excel_bytes = _make_excel_bytes()
    result = _parse_na_rig_count(excel_bytes)

    for key, df in result.items():
        assert len(df) == 1, f"{key} expected 1 row, got {len(df)}"


def test_parse_correct_values():
    excel_bytes = _make_excel_bytes(
        date_str="2024-01-05",
        us_total=600,
        us_oil=480,
        us_gas=110,
        canada=190,
    )
    result = _parse_na_rig_count(excel_bytes)

    assert int(result["BHI_US_TOTAL_RIGS"]["count"].iloc[0]) == 600
    assert int(result["BHI_US_OIL_RIGS"]["count"].iloc[0]) == 480
    assert int(result["BHI_CANADA_RIGS"]["count"].iloc[0]) == 190


def test_parse_raises_on_missing_sheet():
    excel_bytes = _make_excel_bytes(sheet_name="Wrong Sheet")
    with pytest.raises(Exception):
        _parse_na_rig_count(excel_bytes)


def test_parse_raises_on_missing_date():
    """Excel with no date in row 3 col 3 raises an exception."""
    excel_bytes = _make_excel_bytes(date_str=None)
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
    excel_bytes = _make_excel_bytes()
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
    excel_bytes = _make_excel_bytes()
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
    """If existing data is older than the snapshot date, collect writes 1 new row."""
    # Snapshot is 2024-01-19; existing data ends at 2024-01-05 → new row expected
    excel_bytes = _make_excel_bytes(date_str="2024-01-19", us_total=598, us_oil=478, us_gas=109, canada=188)

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

    # Snapshot date (2024-01-19) > existing last date (2024-01-05) → 1 new row per series
    for key in SERIES_KEYS:
        assert key in written
        assert len(written[key]) == 1, f"{key}: expected 1 new row, got {len(written[key])}"


def test_collect_idempotent_no_write_when_fully_up_to_date():
    """If last stored date matches the snapshot date, write_series is not called."""
    excel_bytes = _make_excel_bytes(date_str="2024-01-19", us_total=598, us_oil=478, us_gas=109, canada=188)

    # Last stored date matches the snapshot date → no new rows
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
    """collect() does not call write_series when Excel has no parseable date."""
    # date_str=None → no date in row 3 col 3 → parse raises ValueError → collect skips
    excel_bytes = _make_excel_bytes(date_str=None)

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
    excel_bytes = _make_excel_bytes()
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
