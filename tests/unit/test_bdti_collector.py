# mypy: ignore-errors
"""
Unit tests for the BDTI (Baltic Dirty Tanker Index) collector.
All network calls and store writes are mocked — no live requests in tests.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.bdti import ARC_KEY, STOCKQ_URL, _fetch_bdti, collect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _html_with_value(value: str) -> str:
    """Minimal StockQ-like HTML containing a numeric cell."""
    return f"<html><body><table><tr><td>{value}</td></tr></table></body></html>"


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_arc_key_value():
    assert ARC_KEY == "BDTI_1D"


def test_stockq_url_contains_bdti():
    assert "BDTI" in STOCKQ_URL


# ---------------------------------------------------------------------------
# _fetch_bdti
# ---------------------------------------------------------------------------


def test_fetch_bdti_returns_float():
    resp = _mock_response(_html_with_value("1,107.00"))
    with patch("data.collectors.bdti.requests.get", return_value=resp):
        result = _fetch_bdti()
    assert isinstance(result, float)
    assert result == 1107.0


def test_fetch_bdti_parses_value_in_range():
    resp = _mock_response(_html_with_value("850"))
    with patch("data.collectors.bdti.requests.get", return_value=resp):
        result = _fetch_bdti()
    assert 200 <= result <= 10000


def test_fetch_bdti_raises_value_error_when_no_valid_number():
    resp = _mock_response("<html><body><td>N/A</td></body></html>")
    with patch("data.collectors.bdti.requests.get", return_value=resp):
        with pytest.raises(ValueError, match="Could not parse"):
            _fetch_bdti()


def test_fetch_bdti_raises_on_http_error():
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("403 Forbidden")
    with patch("data.collectors.bdti.requests.get", return_value=resp):
        with pytest.raises(Exception, match="403"):
            _fetch_bdti()


def test_fetch_bdti_ignores_out_of_range_values():
    # Values outside 200–10000 should be skipped; only 900 should match
    html = "<html><body><td>50</td><td>900</td><td>99999</td></body></html>"
    resp = _mock_response(html)
    with patch("data.collectors.bdti.requests.get", return_value=resp):
        result = _fetch_bdti()
    assert result == 900.0


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def test_collect_writes_single_row_with_today():
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    with (
        patch("data.collectors.bdti._fetch_bdti", return_value=1107.0),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
    ):
        collect()

    mock_store.write_series.assert_called_once()
    lib, key, df = mock_store.write_series.call_args[0]
    assert lib == "macro"
    assert key == "BDTI_1D"
    assert len(df) == 1
    assert list(df.columns) == ["value"]
    assert df["value"].iloc[0] == 1107.0


def test_collect_written_df_has_utc_datetime_index():
    written: dict = {}
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = lambda lib, key, df: written.update({"df": df})

    with (
        patch("data.collectors.bdti._fetch_bdti", return_value=900.0),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
    ):
        collect()

    df = written["df"]
    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz == UTC


def test_collect_skips_write_when_today_already_stored():
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = pd.DataFrame(
        {"value": [1000.0]},
        index=pd.DatetimeIndex([today]),
    )
    mock_store = MagicMock()
    mock_store.read_series.return_value = existing

    with (
        patch("data.collectors.bdti._fetch_bdti") as mock_fetch,
        patch("data.collectors.bdti.get_store", return_value=mock_store),
    ):
        collect()

    mock_fetch.assert_not_called()
    mock_store.write_series.assert_not_called()


def test_collect_writes_when_existing_data_is_stale():
    old_date = pd.Timestamp("2025-01-01", tz="UTC")
    existing = pd.DataFrame({"value": [800.0]}, index=pd.DatetimeIndex([old_date]))
    mock_store = MagicMock()
    mock_store.read_series.return_value = existing

    with (
        patch("data.collectors.bdti._fetch_bdti", return_value=1107.0),
        patch("data.collectors.bdti.get_store", return_value=mock_store),
    ):
        collect()

    mock_store.write_series.assert_called_once()
