# mypy: ignore-errors
"""Unit tests for research/graph_export.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from research.graph_export import (
    COLUMN_ALIASES,
    REQUIRED_FIELDS,
    write_baseline_csv,
    write_grid_csv,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_df(**overrides) -> pd.DataFrame:
    """Return a one-row DataFrame with all required run fields."""
    row = {
        "sharpe": 1.5,
        "win_rate": 0.55,
        "profit_factor": 1.8,
        "max_drawdown": -0.12,
        "total_trades": 40,
        "first_trade_ts": "2024-01-02T10:00:00Z",
        "last_trade_ts": "2025-10-01T16:00:00Z",
    }
    row.update(overrides)
    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# write_baseline_csv: required field validation
# ---------------------------------------------------------------------------


class TestWriteBaselineCsvValidation:
    def test_raises_before_writing_when_sharpe_missing(self, tmp_path: Path):
        df = _minimal_df()
        df = df.drop(columns=["sharpe"])
        out = tmp_path / "out.csv"

        with pytest.raises(ValueError, match="sharpe"):
            write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert not out.exists()

    def test_raises_before_writing_when_win_rate_missing(self, tmp_path: Path):
        df = _minimal_df()
        df = df.drop(columns=["win_rate"])
        out = tmp_path / "out.csv"

        with pytest.raises(ValueError, match="win_rate"):
            write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert not out.exists()

    def test_raises_on_empty_dataframe(self, tmp_path: Path):
        df = pd.DataFrame()
        out = tmp_path / "out.csv"

        with pytest.raises(ValueError, match="empty"):
            write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert not out.exists()

    def test_raises_on_invalid_direction(self, tmp_path: Path):
        df = _minimal_df()
        out = tmp_path / "out.csv"

        with pytest.raises(ValueError, match="Invalid direction"):
            write_baseline_csv(df, out, "CL", "1H", "short_bear", "liquidity-sweep")

        assert not out.exists()

    def test_valid_directions_accepted(self, tmp_path: Path):
        for direction in ("long", "short", "bear", "bull"):
            df = _minimal_df()
            out = tmp_path / f"out_{direction}.csv"
            write_baseline_csv(df, out, "ES", "1H", direction, "baseline")
            assert out.exists()


# ---------------------------------------------------------------------------
# write_baseline_csv: alias mapping
# ---------------------------------------------------------------------------


class TestWriteBaselineCsvAliases:
    def test_n_trades_becomes_total_trades(self, tmp_path: Path):
        df = _minimal_df()
        df = df.drop(columns=["total_trades"])
        df["n_trades"] = 35
        out = tmp_path / "out.csv"

        write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        assert "total_trades" in result.columns
        assert "n_trades" not in result.columns
        assert int(result["total_trades"].iloc[0]) == 35

    def test_n_becomes_total_trades(self, tmp_path: Path):
        df = _minimal_df()
        df = df.drop(columns=["total_trades"])
        df["n"] = 22
        out = tmp_path / "out.csv"

        write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        assert "total_trades" in result.columns
        assert int(result["total_trades"].iloc[0]) == 22

    def test_max_dd_becomes_max_drawdown(self, tmp_path: Path):
        df = _minimal_df()
        df = df.drop(columns=["max_drawdown"])
        df["max_dd"] = -0.08
        out = tmp_path / "out.csv"

        write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        assert "max_drawdown" in result.columns
        assert "max_dd" not in result.columns


# ---------------------------------------------------------------------------
# write_baseline_csv: metadata injection
# ---------------------------------------------------------------------------


class TestWriteBaselineCsvMetadata:
    def test_strategy_metadata_injected(self, tmp_path: Path):
        df = _minimal_df()
        out = tmp_path / "out.csv"

        write_baseline_csv(df, out, "ES", "4H", "bull", "mars")

        result = pd.read_csv(out)
        assert result["instrument"].iloc[0] == "ES"
        assert result["timeframe"].iloc[0] == "4H"
        assert result["direction"].iloc[0] == "bull"
        assert result["logic_type"].iloc[0] == "mars"

    def test_returns_output_path(self, tmp_path: Path):
        df = _minimal_df()
        out = tmp_path / "out.csv"

        returned = write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert returned == out

    def test_creates_parent_directories(self, tmp_path: Path):
        df = _minimal_df()
        out = tmp_path / "a" / "b" / "c" / "out.csv"

        write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert out.exists()

    def test_optional_columns_preserved(self, tmp_path: Path):
        df = _minimal_df()
        df["calmar"] = 3.5
        df["return"] = 0.12
        df["tier"] = "professional"
        out = tmp_path / "out.csv"

        write_baseline_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        assert pytest.approx(result["calmar"].iloc[0]) == 3.5
        assert pytest.approx(result["return"].iloc[0]) == 0.12
        assert result["tier"].iloc[0] == "professional"


# ---------------------------------------------------------------------------
# write_grid_csv
# ---------------------------------------------------------------------------


class TestWriteGridCsv:
    def _grid_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "label": "mode_a",
                    "sharpe": 1.2,
                    "win_rate": 0.50,
                    "profit_factor": 1.5,
                    "max_drawdown": -0.10,
                    "total_trades": 30,
                    "first_trade_ts": "2024-01-02T10:00:00Z",
                    "last_trade_ts": "2025-10-01T16:00:00Z",
                    "params_json": {"label": "mode_a", "sizing_mode": "flat"},
                },
                {
                    "label": "mode_b",
                    "sharpe": 1.8,
                    "win_rate": 0.60,
                    "profit_factor": 2.0,
                    "max_drawdown": -0.07,
                    "total_trades": 30,
                    "first_trade_ts": "2024-01-02T10:00:00Z",
                    "last_trade_ts": "2025-10-01T16:00:00Z",
                    "params_json": {"label": "mode_b", "sizing_mode": "rdist"},
                },
            ]
        )

    def test_writes_grid_with_two_rows(self, tmp_path: Path):
        df = self._grid_df()
        out = tmp_path / "grid.csv"

        write_grid_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        assert len(result) == 2

    def test_params_json_dict_serialized_to_string(self, tmp_path: Path):
        df = self._grid_df()
        out = tmp_path / "grid.csv"

        write_grid_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        result = pd.read_csv(out)
        import json

        parsed = json.loads(result["params_json"].iloc[0])
        assert isinstance(parsed, dict)

    def test_raises_on_missing_required_field(self, tmp_path: Path):
        df = self._grid_df().drop(columns=["sharpe"])
        out = tmp_path / "grid.csv"

        with pytest.raises(ValueError, match="sharpe"):
            write_grid_csv(df, out, "CL", "1H", "bear", "liquidity-sweep")

        assert not out.exists()


# ---------------------------------------------------------------------------
# Sync test: REQUIRED_FIELDS matches qws_graph CSV_REQUIRED_ALIASES
# ---------------------------------------------------------------------------


class TestRequiredFieldsSync:
    def test_required_fields_matches_qws_graph_parser(self):
        """REQUIRED_FIELDS must be consistent with qws_graph CSV_REQUIRED_ALIASES.

        This test prevents silent drift between graph_export.py and parsers.py.
        If this test fails, update REQUIRED_FIELDS in research/graph_export.py.
        """
        qws_graph_root = ROOT / "qws_graph"
        if str(qws_graph_root) not in sys.path:
            sys.path.insert(0, str(qws_graph_root))

        from research.graph.parsers import CSV_REQUIRED_ALIASES

        parser_required = frozenset(CSV_REQUIRED_ALIASES.keys())
        # graph_export also requires strategy metadata; strip those out for comparison
        run_required = REQUIRED_FIELDS - {"instrument", "timeframe", "direction", "logic_type"}
        assert run_required == parser_required, (
            f"graph_export REQUIRED_FIELDS run fields {sorted(run_required)} "
            f"!= parsers CSV_REQUIRED_ALIASES {sorted(parser_required)}"
        )

    def test_column_aliases_covers_n_trades(self):
        assert "n_trades" in COLUMN_ALIASES
        assert COLUMN_ALIASES["n_trades"] == "total_trades"
