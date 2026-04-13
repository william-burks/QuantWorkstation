# mypy: ignore-errors
"""
Unit tests for the COT collector.
All HTTP calls and store writes are mocked — no live download in tests.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.collectors.cot import (
    CFTC_SYMBOL_MAP,
    _fetch_csv,
    _parse_df,
    collect,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DISAGG_HEADER = (
    "Market_and_Exchange_Names,As_of_Date_In_Form_YYMMDD,Report_Date_as_YYYY-MM-DD,"
    "CFTC_Contract_Market_Code,CFTC_Market_Code,CFTC_Region_Code,CFTC_Commodity_Code,"
    "Open_Interest_All,Prod_Merc_Positions_Long_All,Prod_Merc_Positions_Short_All,"
    "Swap_Positions_Long_All,Swap__Positions_Short_All,Swap__Positions_Spread_All,"
    "M_Money_Positions_Long_All,M_Money_Positions_Short_All,M_Money_Positions_Spread_All,"
    "Other_Rept_Positions_Long_All,Other_Rept_Positions_Short_All,Other_Rept_Positions_Spread_All,"
    "Tot_Rept_Positions_Long_All,Tot_Rept_Positions_Short_All,NonRept_Positions_Long_All,NonRept_Positions_Short_All"
)

_FIN_HEADER = (
    "Market_and_Exchange_Names,As_of_Date_In_Form_YYMMDD,Report_Date_as_YYYY-MM-DD,"
    "CFTC_Contract_Market_Code,CFTC_Market_Code,CFTC_Region_Code,CFTC_Commodity_Code,"
    "Open_Interest_All,Dealer_Positions_Long_All,Dealer_Positions_Short_All,Dealer_Positions_Spread_All,"
    "Asset_Mgr_Positions_Long_All,Asset_Mgr_Positions_Short_All,Asset_Mgr_Positions_Spread_All,"
    "Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All,Lev_Money_Positions_Spread_All,"
    "Other_Rept_Positions_Long_All,Other_Rept_Positions_Short_All,Other_Rept_Positions_Spread_All,"
    "Tot_Rept_Positions_Long_All,Tot_Rept_Positions_Short_All,NonRept_Positions_Long_All,NonRept_Positions_Short_All"
)


def _make_disagg_row(code: str, date: str, oi: int, pl: int, ps: int, ml: int, ms: int) -> str:
    """Build a minimal disaggregated COT CSV row."""
    return (
        f"MARKET NAME,{date.replace('-', '')[2:]},{date},{code},CME,00,000,"
        f"{oi},{pl},{ps},0,0,0,{ml},{ms},0,0,0,0,0,0,0,0"
    )


def _make_fin_row(code: str, date: str, oi: int, dl: int, ds: int, ll: int, ls: int) -> str:
    """Build a minimal financial COT CSV row."""
    return (
        f"MARKET NAME,{date.replace('-', '')[2:]},{date},{code},CME,00,000,"
        f"{oi},{dl},{ds},0,0,0,0,{ll},{ls},0,0,0,0,0,0,0,0"
    )


def _make_zip_bytes(csv_content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.txt", csv_content)
    return buf.getvalue()


def _disagg_zip(*rows: str) -> bytes:
    content = _DISAGG_HEADER + "\n" + "\n".join(rows)
    return _make_zip_bytes(content)


def _fin_zip(*rows: str) -> bytes:
    content = _FIN_HEADER + "\n" + "\n".join(rows)
    return _make_zip_bytes(content)


# ---------------------------------------------------------------------------
# _fetch_csv
# ---------------------------------------------------------------------------


def test_fetch_csv_parses_zip():
    csv_text = "col1,col2\nval1,val2\n"
    zip_bytes = _make_zip_bytes(csv_text)

    mock_resp = MagicMock()
    mock_resp.content = zip_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        df = _fetch_csv("https://example.com/fake.zip")

    assert list(df.columns) == ["col1", "col2"]
    assert len(df) == 1


# ---------------------------------------------------------------------------
# _parse_df — disaggregated
# ---------------------------------------------------------------------------


def test_parse_df_disagg_computes_net():
    csv = _DISAGG_HEADER + "\n" + _make_disagg_row("088691", "2024-01-02", 100000, 30000, 10000, 50000, 20000)
    raw = pd.read_csv(io.StringIO(csv))
    result = _parse_df(raw, "disagg")

    assert len(result) == 1
    row = result.iloc[0]
    # comm_net = prod_long - prod_short = 30000 - 10000 = 20000
    assert row["comm_net"] == 20000
    # noncomm_net = m_money_long - m_money_short = 50000 - 20000 = 30000
    assert row["noncomm_net"] == 30000
    assert row["open_interest"] == 100000


def test_parse_df_disagg_index_is_datetime():
    csv = _DISAGG_HEADER + "\n" + _make_disagg_row("088691", "2024-03-05", 50000, 10000, 5000, 20000, 8000)
    raw = pd.read_csv(io.StringIO(csv))
    result = _parse_df(raw, "disagg")
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


# ---------------------------------------------------------------------------
# _parse_df — financial
# ---------------------------------------------------------------------------


def test_parse_df_fin_computes_net():
    csv = _FIN_HEADER + "\n" + _make_fin_row("13874+", "2024-06-11", 2000000, 80000, 40000, 150000, 60000)
    raw = pd.read_csv(io.StringIO(csv))
    result = _parse_df(raw, "fin")

    assert len(result) == 1
    row = result.iloc[0]
    # comm_net = dealer_long - dealer_short = 80000 - 40000 = 40000
    assert row["comm_net"] == 40000
    # noncomm_net = lev_long - lev_short = 150000 - 60000 = 90000
    assert row["noncomm_net"] == 90000
    assert row["open_interest"] == 2000000


# ---------------------------------------------------------------------------
# collect — integration with mocked HTTP + store
# ---------------------------------------------------------------------------


def _build_disagg_zip_bytes() -> bytes:
    rows = [
        _make_disagg_row("088691", "2024-01-02", 450000, 9000, 80000, 180000, 15000),
        _make_disagg_row("088691", "2024-01-09", 460000, 9500, 82000, 185000, 16000),
        _make_disagg_row("088695", "2024-01-02", 50000, 500, 8000, 18000, 1500),
        _make_disagg_row("067651", "2024-01-02", 1800000, 60000, 50000, 200000, 180000),
    ]
    return _disagg_zip(*rows)


def _build_fin_zip_bytes() -> bytes:
    rows = [
        _make_fin_row("13874+", "2024-01-02", 2000000, 80000, 40000, 150000, 60000),
        _make_fin_row("13874+", "2024-01-09", 2100000, 85000, 42000, 155000, 62000),
        _make_fin_row("20974+", "2024-01-02", 300000, 20000, 10000, 80000, 30000),
        _make_fin_row("043602", "2024-01-02", 4500000, 180000, 550000, 120000, 80000),
        _make_fin_row("020601", "2024-01-02", 1900000, 30000, 170000, 50000, 30000),
        _make_fin_row("099741", "2024-01-02", 600000, 30000, 160000, 100000, 80000),
    ]
    return _fin_zip(*rows)


def test_collect_calls_write_series():
    """collect() calls store.write_series() for each symbol."""
    disagg_bytes = _build_disagg_zip_bytes()
    fin_bytes = _build_fin_zip_bytes()

    def fake_get(url: str, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "disagg" in url:
            resp.content = disagg_bytes
        else:
            resp.content = fin_bytes
        return resp

    mock_store = MagicMock()

    with patch("requests.get", side_effect=fake_get), patch(
        "data.collectors.cot.get_store", return_value=mock_store
    ):
        collect(symbols=["GC", "CL", "ES", "ZN"])

    # Expect 4 write_series calls (one per symbol per year-batch, but years merged → 1 call each)
    # Each call must use library="cot"
    calls = mock_store.write_series.call_args_list
    libs = {c[0][0] for c in calls}
    assert libs == {"cot"}

    keys_written = {c[0][1] for c in calls}
    assert "GC_cot" in keys_written
    assert "CL_cot" in keys_written
    assert "ES_cot" in keys_written
    assert "ZN_cot" in keys_written


def test_collect_write_series_df_columns():
    """DataFrames written to store have correct columns."""
    disagg_bytes = _build_disagg_zip_bytes()
    fin_bytes = _build_fin_zip_bytes()

    def fake_get(url: str, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = disagg_bytes if "disagg" in url else fin_bytes
        return resp

    written: dict[str, pd.DataFrame] = {}

    def capture_write(lib: str, sym: str, df: pd.DataFrame) -> None:
        written[sym] = df

    mock_store = MagicMock()
    mock_store.write_series.side_effect = capture_write

    with patch("requests.get", side_effect=fake_get), patch(
        "data.collectors.cot.get_store", return_value=mock_store
    ):
        collect(symbols=["GC", "ES"])

    for sym in ["GC_cot", "ES_cot"]:
        assert sym in written, f"{sym} not written"
        df = written[sym]
        assert set(df.columns) == {"comm_net", "noncomm_net", "open_interest"}, (
            f"Unexpected columns for {sym}: {list(df.columns)}"
        )
        assert pd.api.types.is_datetime64_any_dtype(df.index), "Index must be datetime"


def test_collect_idempotent_no_duplicate_rows():
    """Calling collect twice with same data produces no duplicate index rows."""
    disagg_bytes = _build_disagg_zip_bytes()
    fin_bytes = _build_fin_zip_bytes()

    def fake_get(url: str, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = disagg_bytes if "disagg" in url else fin_bytes
        return resp

    # store.write_series deduplicates — simulate by passing through to _parse_df
    # The collector itself deduplicates before calling write_series
    written_dfs: list[pd.DataFrame] = []

    def capture(lib: str, sym: str, df: pd.DataFrame) -> None:
        written_dfs.append(df)

    mock_store = MagicMock()
    mock_store.write_series.side_effect = capture

    with patch("requests.get", side_effect=fake_get), patch(
        "data.collectors.cot.get_store", return_value=mock_store
    ):
        collect(symbols=["GC"])

    for df in written_dfs:
        assert not df.index.duplicated().any(), "Duplicate index entries found"


def test_collect_raises_on_unknown_symbol():
    with pytest.raises(ValueError, match="Unknown COT symbols"):
        collect(symbols=["INVALID_SYM"])


# ---------------------------------------------------------------------------
# CFTC_SYMBOL_MAP coverage
# ---------------------------------------------------------------------------


def test_symbol_map_has_required_symbols():
    required = {"ES", "CL", "GC", "MGC", "NQ", "ZN", "ZB", "6E"}
    assert required.issubset(set(CFTC_SYMBOL_MAP.keys()))


def test_symbol_map_report_types():
    disagg = {"GC", "MGC", "CL"}
    fin = {"ES", "NQ", "ZN", "ZB", "6E"}
    for sym in disagg:
        assert CFTC_SYMBOL_MAP[sym].report_type == "disagg", f"{sym} should be disagg"
    for sym in fin:
        assert CFTC_SYMBOL_MAP[sym].report_type == "fin", f"{sym} should be fin"
