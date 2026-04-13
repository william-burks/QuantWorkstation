# mypy: ignore-errors
"""
Unit tests for the Google Trends collector.
All pytrends.TrendReq calls and store writes are mocked — no live requests.
"""

from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from data.collectors.google_trends import (
    DEFAULT_TERMS,
    _arc_key,
    _fetch_term,
    collect,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trends_df(term: str, dates: list[str], values: list[int]) -> pd.DataFrame:
    """Build a DataFrame matching pytrends interest_over_time() output."""
    idx = pd.to_datetime(dates)
    df = pd.DataFrame({term: values, "isPartial": [False] * len(dates)}, index=idx)
    return df


def _make_mock_trendreq(term: str, dates: list[str], values: list[int]) -> MagicMock:
    """Return a mock TrendReq instance with canned interest_over_time output."""
    raw_df = _make_trends_df(term, dates, values)
    instance = MagicMock()
    instance.interest_over_time.return_value = raw_df
    return instance


# ---------------------------------------------------------------------------
# _arc_key
# ---------------------------------------------------------------------------


def test_arc_key_buy_gold():
    assert _arc_key("buy gold") == "GTRENDS_BUY_GOLD"


def test_arc_key_gold_inflation_hedge():
    assert _arc_key("gold inflation hedge") == "GTRENDS_GOLD_INFLATION_HEDGE"


def test_arc_key_recession():
    assert _arc_key("recession") == "GTRENDS_RECESSION"


def test_arc_key_inflation():
    assert _arc_key("inflation") == "GTRENDS_INFLATION"


def test_arc_key_strips_punctuation():
    # Ensure non-alphanumeric chars (other than underscore) are stripped
    assert _arc_key("buy gold!") == "GTRENDS_BUY_GOLD"


# ---------------------------------------------------------------------------
# _fetch_term
# ---------------------------------------------------------------------------


def test_fetch_term_returns_interest_column():
    mock_instance = _make_mock_trendreq("buy gold", ["2024-01-01", "2024-01-08"], [45, 50])

    with patch("data.collectors.google_trends.TrendReq", return_value=mock_instance):
        df = _fetch_term("buy gold")

    assert "interest" in df.columns
    assert len(df) == 2


def test_fetch_term_index_is_utc():
    mock_instance = _make_mock_trendreq("recession", ["2024-01-01", "2024-01-08"], [30, 35])

    with patch("data.collectors.google_trends.TrendReq", return_value=mock_instance):
        df = _fetch_term("recession")

    assert pd.api.types.is_datetime64_any_dtype(df.index)
    assert df.index.tz is not None  # UTC-aware


def test_fetch_term_interest_is_int():
    mock_instance = _make_mock_trendreq("inflation", ["2024-01-01"], [72])

    with patch("data.collectors.google_trends.TrendReq", return_value=mock_instance):
        df = _fetch_term("inflation")

    assert df["interest"].dtype == int or pd.api.types.is_integer_dtype(df["interest"])
    assert df["interest"].iloc[0] == 72


def test_fetch_term_empty_response_returns_empty_df():
    instance = MagicMock()
    instance.interest_over_time.return_value = pd.DataFrame()

    with patch("data.collectors.google_trends.TrendReq", return_value=instance):
        df = _fetch_term("buy gold")

    assert df.empty
    assert "interest" in df.columns


def test_fetch_term_retries_on_response_error():
    """On ResponseError, sleep 120s and retry once; second success returns data."""
    from pytrends.exceptions import ResponseError as _ResponseError  # type: ignore[import-untyped]

    call_count = [0]
    good_df = _make_trends_df("buy gold", ["2024-01-01"], [55])

    def side_effect(*args, **kwargs):  # noqa: ARG001
        call_count[0] += 1
        if call_count[0] == 1:
            raise _ResponseError(message="Too many requests", response=MagicMock())
        return good_df

    instance = MagicMock()
    instance.interest_over_time.side_effect = side_effect

    with (
        patch("data.collectors.google_trends.TrendReq", return_value=instance),
        patch("data.collectors.google_trends.time.sleep") as mock_sleep,
    ):
        df = _fetch_term("buy gold")

    assert not df.empty
    assert df["interest"].iloc[0] == 55
    mock_sleep.assert_called_once_with(120.0)


def test_fetch_term_skips_on_double_response_error():
    """Two consecutive ResponseErrors → returns empty DataFrame (graceful skip)."""
    from pytrends.exceptions import ResponseError as _ResponseError  # type: ignore[import-untyped]

    err = _ResponseError(message="Too many requests", response=MagicMock())
    instance = MagicMock()
    instance.interest_over_time.side_effect = err

    with (
        patch("data.collectors.google_trends.TrendReq", return_value=instance),
        patch("data.collectors.google_trends.time.sleep"),
    ):
        df = _fetch_term("buy gold")

    assert df.empty
    assert "interest" in df.columns


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def _mock_trendreq_for(term: str) -> MagicMock:
    dates = ["2024-01-01", "2024-01-08", "2024-01-15"]
    values = [40, 50, 60]
    return _make_mock_trendreq(term, dates, values)


def test_collect_writes_four_default_terms():
    """collect() calls store.write_series() once per default term."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    instances = {term: _mock_trendreq_for(term) for term in DEFAULT_TERMS}
    call_idx = [0]

    def make_instance(*args, **kwargs):  # noqa: ARG001
        term = DEFAULT_TERMS[call_idx[0] % len(DEFAULT_TERMS)]
        call_idx[0] += 1
        return instances[term]

    with (
        patch("data.collectors.google_trends.TrendReq", side_effect=make_instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep"),
    ):
        mock_settings.return_value.gtrends_terms = list(DEFAULT_TERMS)
        collect()

    assert mock_store.write_series.call_count == 4
    libs = {c[0][0] for c in mock_store.write_series.call_args_list}
    assert libs == {"macro"}


def test_collect_writes_correct_arc_keys():
    """Written keys match expected GTRENDS_ slugs for default terms."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    instances = {term: _mock_trendreq_for(term) for term in DEFAULT_TERMS}
    call_idx = [0]

    def make_instance(*args, **kwargs):  # noqa: ARG001
        term = DEFAULT_TERMS[call_idx[0] % len(DEFAULT_TERMS)]
        call_idx[0] += 1
        return instances[term]

    with (
        patch("data.collectors.google_trends.TrendReq", side_effect=make_instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep"),
    ):
        mock_settings.return_value.gtrends_terms = list(DEFAULT_TERMS)
        collect()

    keys_written = {c[0][1] for c in mock_store.write_series.call_args_list}
    assert keys_written == {
        "GTRENDS_BUY_GOLD",
        "GTRENDS_GOLD_INFLATION_HEDGE",
        "GTRENDS_RECESSION",
        "GTRENDS_INFLATION",
    }


def test_collect_written_df_has_interest_column_and_datetime_index():
    """DataFrames written to store have 'interest' column and DatetimeIndex."""
    written: dict[str, pd.DataFrame] = {}

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")
    mock_store.write_series.side_effect = capture

    instance = _mock_trendreq_for("buy gold")

    with (
        patch("data.collectors.google_trends.TrendReq", return_value=instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep"),
    ):
        mock_settings.return_value.gtrends_terms = ["buy gold"]
        collect()

    assert "GTRENDS_BUY_GOLD" in written
    df = written["GTRENDS_BUY_GOLD"]
    assert "interest" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_collect_skips_write_when_empty():
    """If fetch returns empty DataFrame, write_series is not called."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    instance = MagicMock()
    instance.interest_over_time.return_value = pd.DataFrame()

    with (
        patch("data.collectors.google_trends.TrendReq", return_value=instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep"),
    ):
        mock_settings.return_value.gtrends_terms = ["buy gold"]
        collect()

    mock_store.write_series.assert_not_called()


def test_collect_sleeps_between_terms():
    """60s sleep is called between term fetches (not after last term)."""
    mock_store = MagicMock()
    mock_store.read_series.side_effect = Exception("not found")

    instances = {term: _mock_trendreq_for(term) for term in DEFAULT_TERMS}
    call_idx = [0]

    def make_instance(*args, **kwargs):  # noqa: ARG001
        term = DEFAULT_TERMS[call_idx[0] % len(DEFAULT_TERMS)]
        call_idx[0] += 1
        return instances[term]

    with (
        patch("data.collectors.google_trends.TrendReq", side_effect=make_instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep") as mock_sleep,
    ):
        mock_settings.return_value.gtrends_terms = list(DEFAULT_TERMS)
        collect()

    # 4 terms → 3 sleeps (not after last)
    sleep_calls = [c for c in mock_sleep.call_args_list if c[0][0] == 60.0]
    assert len(sleep_calls) == 3


def test_collect_upsert_deduplicates_index():
    """Re-running with overlapping dates produces no duplicate index entries."""
    existing_dates = ["2024-01-01", "2024-01-08"]
    existing_df = pd.DataFrame(
        {"interest": [40, 50]},
        index=pd.to_datetime(existing_dates).tz_localize("UTC"),
    )

    written_dfs: list[pd.DataFrame] = []

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written_dfs.append(df)

    mock_store = MagicMock()
    mock_store.read_series.return_value = existing_df
    mock_store.write_series.side_effect = capture

    # New fetch includes overlapping + new week
    new_dates = ["2024-01-08", "2024-01-15"]
    instance = _make_mock_trendreq("buy gold", new_dates, [55, 65])

    with (
        patch("data.collectors.google_trends.TrendReq", return_value=instance),
        patch("data.collectors.google_trends.get_store", return_value=mock_store),
        patch("data.collectors.google_trends.get_settings") as mock_settings,
        patch("data.collectors.google_trends.time.sleep"),
    ):
        mock_settings.return_value.gtrends_terms = ["buy gold"]
        collect()

    assert len(written_dfs) == 1
    result = written_dfs[0]
    # No duplicate index
    assert result.index.duplicated().sum() == 0
    # All 3 distinct dates present
    assert len(result) == 3
    # Overlap row uses new value (55, not 50)
    overlap_ts = pd.Timestamp("2024-01-08", tz="UTC")
    assert result.loc[overlap_ts, "interest"] == 55


# ---------------------------------------------------------------------------
# DEFAULT_TERMS
# ---------------------------------------------------------------------------


def test_default_terms_has_four_expected_values():
    expected = {"buy gold", "gold inflation hedge", "recession", "inflation"}
    assert set(DEFAULT_TERMS) == expected
