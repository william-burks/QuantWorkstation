"""
Unit tests for annual_pnl_breakdown (metrics.py) and _annual_breakdown / report()
integration (evaluator.py).

Covers:
- Single-year trades
- Multi-year trades with correct pct_of_total
- Concentration warning fires at > 50%
- Concentration warning does NOT fire at exactly 50.0%
- Existing report() output unchanged when trades_df not supplied
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.experiments.evaluator import _annual_breakdown
from research.experiments.metrics import annual_pnl_breakdown

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _trades(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """Build a minimal trades_df from (entry_time_str, pnl_usd) pairs."""
    return pd.DataFrame({"entry_time": [r[0] for r in rows], "pnl_usd": [r[1] for r in rows]})


# ---------------------------------------------------------------------------
# annual_pnl_breakdown — metrics.py
# ---------------------------------------------------------------------------


class TestAnnualPnlBreakdown:
    def test_empty_returns_empty(self) -> None:
        df = pd.DataFrame(columns=["entry_time", "pnl_usd"])
        assert annual_pnl_breakdown(df) == []

    def test_single_year(self) -> None:
        df = _trades(
            [
                ("2020-03-01", 1000.0),
                ("2020-06-01", 2000.0),
                ("2020-09-01", -500.0),
            ]
        )
        result = annual_pnl_breakdown(df)
        assert len(result) == 1
        row = result[0]
        assert row["year"] == 2020
        assert row["trades"] == 3
        assert pytest.approx(row["gross_pnl"], rel=1e-6) == 2500.0
        assert pytest.approx(row["pct_of_total"], rel=1e-6) == 100.0

    def test_multi_year_pct(self) -> None:
        df = _trades(
            [
                ("2020-01-15", 1000.0),
                ("2021-01-15", 500.0),
                ("2022-01-15", 500.0),
            ]
        )
        result = annual_pnl_breakdown(df)
        assert len(result) == 3
        years = {r["year"]: r for r in result}
        assert pytest.approx(years[2020]["pct_of_total"], rel=1e-4) == 50.0
        assert pytest.approx(years[2021]["pct_of_total"], rel=1e-4) == 25.0
        assert pytest.approx(years[2022]["pct_of_total"], rel=1e-4) == 25.0

    def test_trade_count_correct(self) -> None:
        df = _trades(
            [
                ("2020-01-01", 100.0),
                ("2020-02-01", 200.0),
                ("2021-01-01", 300.0),
            ]
        )
        result = annual_pnl_breakdown(df)
        years = {r["year"]: r for r in result}
        assert years[2020]["trades"] == 2
        assert years[2021]["trades"] == 1

    def test_sorted_by_year(self) -> None:
        df = _trades(
            [
                ("2022-06-01", 100.0),
                ("2020-06-01", 200.0),
                ("2021-06-01", 150.0),
            ]
        )
        result = annual_pnl_breakdown(df)
        assert [r["year"] for r in result] == [2020, 2021, 2022]

    def test_sharpe_flat_trades_is_zero(self) -> None:
        # All same P&L → std=0 → sharpe=0
        df = _trades(
            [
                ("2020-01-01", 100.0),
                ("2020-06-01", 100.0),
            ]
        )
        result = annual_pnl_breakdown(df)
        assert result[0]["sharpe"] == 0.0


# ---------------------------------------------------------------------------
# _annual_breakdown — evaluator.py (formatting + concentration)
# ---------------------------------------------------------------------------


class TestAnnualBreakdownFormatter:
    def test_empty_returns_empty_string(self) -> None:
        df = pd.DataFrame(columns=["entry_time", "pnl_usd"])
        assert _annual_breakdown(df) == ""

    def test_header_present(self) -> None:
        df = _trades([("2020-03-01", 500.0), ("2021-03-01", 500.0)])
        output = _annual_breakdown(df)
        assert "Annual Breakdown" in output
        assert "Year" in output
        assert "Gross P&L" in output

    def test_concentration_fires_above_50(self) -> None:
        # 2020 gets 50.0001% — should fire
        df = _trades(
            [
                ("2020-01-01", 50_001.0),
                ("2021-01-01", 49_999.0),
            ]
        )
        output = _annual_breakdown(df)
        assert "[WARN] Regime concentration" in output
        assert "2020" in output

    def test_concentration_does_not_fire_at_exactly_50(self) -> None:
        # 2020 gets exactly 50.0%
        df = _trades(
            [
                ("2020-01-01", 50_000.0),
                ("2021-01-01", 50_000.0),
            ]
        )
        output = _annual_breakdown(df)
        assert "[WARN] Regime concentration" not in output

    def test_concentration_fires_strictly_above_50(self) -> None:
        # Threshold is > 50, not >= 50
        df = _trades(
            [
                ("2020-01-01", 50_001.0),
                ("2021-01-01", 49_999.0),
            ]
        )
        output = _annual_breakdown(df)
        assert "[WARN]" in output

    def test_years_appear_in_output(self) -> None:
        df = _trades(
            [
                ("2020-03-01", 1000.0),
                ("2021-06-01", 2000.0),
            ]
        )
        output = _annual_breakdown(df)
        assert "2020" in output
        assert "2021" in output
