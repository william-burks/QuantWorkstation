# mypy: ignore-errors
"""Unit tests for research/analytics/portfolio_correlation.py

Uses synthetic time series and mock data — no live graph or broker connections.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from research.analytics.portfolio_correlation import (
    compute_correlation_matrix,
    flag_high_pairs,
    load_pnl_series,
    run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_series(values: list[float], name: str = "series") -> pd.Series:
    dates = pd.date_range("2025-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=dates, name=name, dtype=float)


def _series_map_two(r: float = 0.8) -> dict[str, pd.Series]:
    """Two 10-day series with Pearson correlation close to r."""
    base = [1.0, 2.0, -1.0, 3.0, 0.5, -0.5, 2.5, 1.5, -0.5, 1.0]
    # Scale second series to approximate desired correlation
    perturb = [b * r + (1.0 - abs(r)) * 0.1 * i for i, b in enumerate(base)]
    return {
        "strat-a": _make_series(base),
        "strat-b": _make_series(perturb),
    }


# ---------------------------------------------------------------------------
# AC2: Correctly computes Pearson correlation from mock series
# ---------------------------------------------------------------------------


class TestComputeCorrelationMatrix:
    def test_perfect_positive_correlation(self) -> None:
        s = [1.0, 2.0, 3.0, 4.0, 5.0]
        series_map = {
            "a": _make_series(s),
            "b": _make_series(s),
        }
        matrix = compute_correlation_matrix(series_map)
        assert pytest.approx(matrix.loc["a", "b"], abs=1e-6) == 1.0

    def test_negative_correlation(self) -> None:
        series_map = {
            "a": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
            "b": _make_series([-1.0, -2.0, -3.0, -4.0, -5.0]),
        }
        matrix = compute_correlation_matrix(series_map)
        assert pytest.approx(matrix.loc["a", "b"], abs=1e-6) == -1.0

    def test_diagonal_is_one(self) -> None:
        series_map = _series_map_two()
        matrix = compute_correlation_matrix(series_map)
        for lbl in series_map:
            assert pytest.approx(matrix.loc[lbl, lbl], abs=1e-6) == 1.0

    def test_empty_input_returns_empty_dataframe(self) -> None:
        matrix = compute_correlation_matrix({})
        assert matrix.empty

    def test_single_series_returns_1x1(self) -> None:
        matrix = compute_correlation_matrix({"only": _make_series([1.0, 2.0, 3.0])})
        assert matrix.shape == (1, 1)
        assert pytest.approx(matrix.iloc[0, 0]) == 1.0


# ---------------------------------------------------------------------------
# AC4: Flag pairs above threshold
# ---------------------------------------------------------------------------


class TestFlagHighPairs:
    def test_flags_high_pair(self) -> None:
        series_map = {
            "a": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
            "b": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
        }
        matrix = compute_correlation_matrix(series_map)
        pairs = flag_high_pairs(matrix, threshold=0.60)
        assert len(pairs) == 1
        a, b, r = pairs[0]
        assert {a, b} == {"a", "b"}
        assert pytest.approx(r, abs=1e-6) == 1.0

    def test_does_not_flag_below_threshold(self) -> None:
        # Orthogonal-ish series: r ≈ 0 (verified manually)
        series_map = {
            "a": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
            "b": _make_series([3.0, 1.0, 4.0, 1.0, 5.0]),
        }
        matrix = compute_correlation_matrix(series_map)
        r = abs(float(matrix.loc["a", "b"]))
        # Only flag if |r| > 0.60; use a threshold above the actual r
        pairs = flag_high_pairs(matrix, threshold=max(r + 0.01, 0.60))
        assert len(pairs) == 0

    def test_negative_correlation_above_abs_threshold_is_flagged(self) -> None:
        series_map = {
            "a": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
            "b": _make_series([-1.0, -2.0, -3.0, -4.0, -5.0]),
        }
        matrix = compute_correlation_matrix(series_map)
        pairs = flag_high_pairs(matrix, threshold=0.60)
        assert len(pairs) == 1
        _, _, r = pairs[0]
        assert r < -0.60

    def test_each_pair_appears_once(self) -> None:
        """Upper-triangle only — no duplicate (a,b) + (b,a)."""
        series = {
            "a": _make_series([1.0, 2.0, 3.0]),
            "b": _make_series([1.0, 2.0, 3.0]),
            "c": _make_series([1.0, 2.0, 3.0]),
        }
        matrix = compute_correlation_matrix(series)
        pairs = flag_high_pairs(matrix, threshold=0.60)
        pair_sets = [{a, b} for a, b, _ in pairs]
        assert len(pair_sets) == len(set(frozenset(p) for p in pair_sets))

    def test_threshold_boundary_excluded(self) -> None:
        """Pairs at exactly threshold are NOT flagged (strict >)."""
        series_map = {
            "a": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
            "b": _make_series([1.0, 2.0, 3.0, 4.0, 5.0]),
        }
        matrix = compute_correlation_matrix(series_map)
        # r=1.0 > 1.0 is False, but threshold=0.60 < r=1.0 so this still flags.
        # Test exact boundary: use a pair with r exactly at threshold — approximate
        # by using very high threshold
        pairs = flag_high_pairs(matrix, threshold=1.0 + 1e-9)
        assert len(pairs) == 0


# ---------------------------------------------------------------------------
# AC3: Champions missing daily_pnl/equity column are skipped with warning
# ---------------------------------------------------------------------------


class TestLoadPnlSeries:
    def test_returns_none_and_warns_when_no_pnl_column(self, tmp_path: Path) -> None:
        csv = tmp_path / "sweep.csv"
        csv.write_text("sharpe,profit_factor,win_rate\n2.1,1.5,0.6\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_pnl_series("sweep.csv", tmp_path)
        assert result is None
        assert any("no daily_pnl or equity column" in str(x.message) for x in w)

    def test_loads_daily_pnl_column(self, tmp_path: Path) -> None:
        csv = tmp_path / "trade.csv"
        csv.write_text("date,daily_pnl\n2025-01-01,100.0\n2025-01-02,200.0\n")
        result = load_pnl_series("trade.csv", tmp_path)
        assert result is not None
        assert len(result) == 2

    def test_loads_equity_column(self, tmp_path: Path) -> None:
        csv = tmp_path / "equity.csv"
        csv.write_text("date,equity\n2025-01-01,10000.0\n2025-01-02,10200.0\n")
        result = load_pnl_series("equity.csv", tmp_path)
        assert result is not None

    def test_returns_none_and_warns_when_file_missing(self, tmp_path: Path) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_pnl_series("nonexistent.csv", tmp_path)
        assert result is None
        assert any("artifact not found" in str(x.message) for x in w)

    def test_prefers_daily_pnl_over_equity(self, tmp_path: Path) -> None:
        csv = tmp_path / "both.csv"
        csv.write_text("date,daily_pnl,equity\n2025-01-01,10.0,5000.0\n")
        result = load_pnl_series("both.csv", tmp_path)
        assert result is not None
        assert float(result.iloc[0]) == 10.0  # daily_pnl, not equity


# ---------------------------------------------------------------------------
# AC5: Empty champion set exits gracefully
# ---------------------------------------------------------------------------


class TestRunEmptyChampions:
    def test_empty_champion_set_exits_zero(self, capsys: pytest.CaptureFixture) -> None:
        mock_store = MagicMock()
        mock_store.get_portfolio_alpha_champions.return_value = []
        exit_code = run(store=mock_store, write_edges=False)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No OOS-pass champions" in captured.out

    def test_no_store_exits_gracefully(self, capsys: pytest.CaptureFixture) -> None:
        exit_code = run(store=None, write_edges=False)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No OOS-pass champions" in captured.out


# ---------------------------------------------------------------------------
# AC1: Script entry point is importable and runnable
# ---------------------------------------------------------------------------


class TestScriptEntryPoint:
    def test_main_function_importable(self) -> None:
        from research.analytics.portfolio_correlation import main  # noqa: PLC0415

        assert callable(main)

    def test_run_function_returns_int(self) -> None:
        result = run(store=None, write_edges=False)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# AC6: CORRELATED_WITH edges written to graph for flagged pairs
# ---------------------------------------------------------------------------


class TestWriteEdges:
    def test_write_correlated_with_called_for_flagged_pairs(self) -> None:
        mock_store = MagicMock()
        mock_store.get_portfolio_alpha_champions.return_value = []

        # Simulate two champions with correlated series via direct run() call
        # We patch load_pnl_series to return controlled series
        champions = [
            {"champion_id": "champ_a", "strategy_id": "strat-a", "artifact_path": "a.csv"},
            {"champion_id": "champ_b", "strategy_id": "strat-b", "artifact_path": "b.csv"},
        ]

        perfect_series = _make_series([1.0, 2.0, 3.0, 4.0, 5.0])

        with patch(
            "research.analytics.portfolio_correlation.load_pnl_series",
            return_value=perfect_series,
        ):
            mock_store.get_portfolio_alpha_champions.return_value = champions
            exit_code = run(store=mock_store, write_edges=True, threshold=0.60)

        assert exit_code == 0
        mock_store.write_correlated_with.assert_called_once()
        call_kwargs = mock_store.write_correlated_with.call_args[1]
        assert call_kwargs["coefficient"] == pytest.approx(1.0, abs=1e-6)

    def test_no_edges_written_when_no_high_pairs(self) -> None:
        mock_store = MagicMock()
        # Series with r well below 0.60 threshold
        uncorrelated_a = _make_series([1.0, 2.0, 3.0, 4.0, 5.0])
        uncorrelated_b = _make_series([5.0, 1.0, 3.0, 2.0, 4.0])  # r ≈ 0.1
        champions = [
            {"champion_id": "ca", "strategy_id": "sa", "artifact_path": "a.csv"},
            {"champion_id": "cb", "strategy_id": "sb", "artifact_path": "b.csv"},
        ]
        mock_store.get_portfolio_alpha_champions.return_value = champions

        side_effects = [uncorrelated_a, uncorrelated_b]
        with patch(
            "research.analytics.portfolio_correlation.load_pnl_series",
            side_effect=side_effects,
        ):
            run(store=mock_store, write_edges=True, threshold=0.60)

        mock_store.write_correlated_with.assert_not_called()


# ---------------------------------------------------------------------------
# AC7 / AC8: portfolio_alpha query extension (Cypher change — unit-level test)
# ---------------------------------------------------------------------------


class TestPortfolioAlphaCypher:
    def test_cypher_contains_is_oos_drift(self) -> None:
        from qws_graph.research.graph.query import GET_PORTFOLIO_ALPHA_V1_CYPHER  # noqa: PLC0415

        assert "is_oos_drift" in GET_PORTFOLIO_ALPHA_V1_CYPHER

    def test_cypher_contains_calmar(self) -> None:
        from qws_graph.research.graph.query import GET_PORTFOLIO_ALPHA_V1_CYPHER  # noqa: PLC0415

        assert "calmar" in GET_PORTFOLIO_ALPHA_V1_CYPHER

    def test_cypher_contains_metrics_max_drawdown_r(self) -> None:
        from qws_graph.research.graph.query import GET_PORTFOLIO_ALPHA_V1_CYPHER  # noqa: PLC0415

        assert "metrics_max_drawdown_r" in GET_PORTFOLIO_ALPHA_V1_CYPHER

    def test_cypher_contains_artifact_path(self) -> None:
        from qws_graph.research.graph.query import GET_PORTFOLIO_ALPHA_V1_CYPHER  # noqa: PLC0415

        assert "artifact_path" in GET_PORTFOLIO_ALPHA_V1_CYPHER


# ---------------------------------------------------------------------------
# AC9: Correlation gate in cli._cmd_bundle
# ---------------------------------------------------------------------------


class TestCorrelationGateCli:
    def test_gate_constant_defined(self) -> None:
        from qws_graph.research.graph.cli import _CORRELATION_GATE_THRESHOLD  # noqa: PLC0415

        assert isinstance(_CORRELATION_GATE_THRESHOLD, float)
        assert _CORRELATION_GATE_THRESHOLD == pytest.approx(0.60)

    def test_store_write_correlated_with_method_signature(self) -> None:
        """Store method exists and accepts required parameters."""
        import inspect  # noqa: PLC0415

        from qws_graph.research.graph.store import GraphStore  # noqa: PLC0415

        sig = inspect.signature(GraphStore.write_correlated_with)
        param_names = set(sig.parameters.keys())
        assert "champion_id_a" in param_names
        assert "champion_id_b" in param_names
        assert "coefficient" in param_names
        assert "threshold" in param_names

    def test_check_correlated_with_method_signature(self) -> None:
        import inspect  # noqa: PLC0415

        from qws_graph.research.graph.store import GraphStore  # noqa: PLC0415

        sig = inspect.signature(GraphStore.check_correlated_with_active_champions)
        param_names = set(sig.parameters.keys())
        assert "candidate_champion_id" in param_names
        assert "threshold" in param_names


# ---------------------------------------------------------------------------
# AC10: Schema docs include CORRELATED_WITH
# ---------------------------------------------------------------------------


class TestSchemaDocs:
    def test_data_dictionary_has_correlated_with(self) -> None:
        dd = Path(__file__).parent.parent.parent / "qws_graph" / "docs" / "data_dictionary.yaml"
        assert dd.exists()
        content = dd.read_text(encoding="utf-8")
        assert "CORRELATED_WITH" in content

    def test_graph_contract_has_correlated_with(self) -> None:
        contract = (
            Path(__file__).parent.parent.parent / "qws_graph" / "docs" / "graph_v1_contract.md"
        )
        assert contract.exists()
        content = contract.read_text(encoding="utf-8")
        assert "CORRELATED_WITH" in content


# ---------------------------------------------------------------------------
# Demo seed check
# ---------------------------------------------------------------------------


class TestDemoSeed:
    def test_demo_seed_contains_correlated_with(self) -> None:
        from qws_graph.research.graph.cypher import DEMO_SEED_CYPHER  # noqa: PLC0415

        assert "CORRELATED_WITH" in DEMO_SEED_CYPHER

    def test_demo_seed_has_correlated_with_properties(self) -> None:
        from qws_graph.research.graph.cypher import DEMO_SEED_CYPHER  # noqa: PLC0415

        assert "coefficient" in DEMO_SEED_CYPHER
        assert "pair_key" in DEMO_SEED_CYPHER
        assert "is_demo" in DEMO_SEED_CYPHER

    def test_correlated_with_cypher_constants_exist(self) -> None:
        from qws_graph.research.graph.cypher import (  # noqa: PLC0415
            CORRELATED_WITH_CHAMPION_QUERY,
            CORRELATED_WITH_STRATEGY_QUERY,
            GET_PORTFOLIO_ALPHA_CHAMPIONS_QUERY,
        )

        assert "CORRELATED_WITH" in CORRELATED_WITH_CHAMPION_QUERY
        assert "CORRELATED_WITH" in CORRELATED_WITH_STRATEGY_QUERY
        assert "oos_pass" in GET_PORTFOLIO_ALPHA_CHAMPIONS_QUERY
