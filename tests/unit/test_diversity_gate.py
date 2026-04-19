"""Unit tests for QWS-1402: regime diversity gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from research.experiments.evaluator import _annual_breakdown, evaluate, report
from research.experiments.metrics import diversity_score

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_THREE_YEAR_BREAKDOWN: list[dict[str, Any]] = [
    {"year": 2022, "trades": 20, "gross_pnl": 1000.0, "sharpe": 1.8, "pct_of_total": 33.3},
    {"year": 2023, "trades": 25, "gross_pnl": 2000.0, "sharpe": 2.1, "pct_of_total": 66.7},
    {"year": 2024, "trades": 15, "gross_pnl": -500.0, "sharpe": -0.5, "pct_of_total": -16.7},
]

_TWO_YEAR_BREAKDOWN: list[dict[str, Any]] = [
    {"year": 2023, "trades": 30, "gross_pnl": 2000.0, "sharpe": 2.5, "pct_of_total": 60.0},
    {"year": 2024, "trades": 25, "gross_pnl": 1500.0, "sharpe": 2.0, "pct_of_total": 40.0},
]

_ONE_YEAR_BREAKDOWN: list[dict[str, Any]] = [
    {"year": 2024, "trades": 50, "gross_pnl": 3000.0, "sharpe": 3.0, "pct_of_total": 100.0},
]

_ONE_YEAR_ZERO_PROFITABLE: list[dict[str, Any]] = [
    {"year": 2024, "trades": 20, "gross_pnl": -500.0, "sharpe": -1.0, "pct_of_total": 100.0},
]


def _make_trades_df(years: list[int], pnls: list[float]) -> pd.DataFrame:
    """Build a minimal trades DataFrame."""
    rows = []
    for year, pnl in zip(years, pnls):
        rows.append({"entry_time": f"{year}-06-15T10:00:00Z", "pnl_usd": pnl})
    return pd.DataFrame(rows)


def _make_results_df() -> pd.DataFrame:
    """Build minimal evaluated sweep results."""
    df = pd.DataFrame(
        {
            "sharpe": [2.5],
            "calmar": [1.5],
            "max_drawdown": [-0.10],
            "return": [0.25],
            "profit_factor": [1.8],
            "win_rate": [0.55],
            "n_trades": [40],
            "gain": [5000.0],
            "fees": [50.0],
        }
    )
    bh = {"sharpe": 0.5, "return": 0.10, "max_drawdown": -0.15, "calmar": 0.5}
    return evaluate(df, bh)


# ---------------------------------------------------------------------------
# AC1: diversity_score() returns correct dict for synthetic fixture
# ---------------------------------------------------------------------------


class TestDiversityScoreMetric:
    def test_three_years_two_profitable(self) -> None:
        result = diversity_score(_THREE_YEAR_BREAKDOWN)
        assert result["diversity_distinct_years"] == 3
        assert result["diversity_years_positive"] == 2
        assert abs(result["diversity_score"] - 2 / 3) < 0.01

    def test_two_years_both_profitable(self) -> None:
        result = diversity_score(_TWO_YEAR_BREAKDOWN)
        assert result["diversity_distinct_years"] == 2
        assert result["diversity_years_positive"] == 2
        assert result["diversity_score"] == 1.0

    def test_one_year_one_profitable(self) -> None:
        result = diversity_score(_ONE_YEAR_BREAKDOWN)
        assert result["diversity_distinct_years"] == 1
        assert result["diversity_years_positive"] == 1
        assert result["diversity_score"] == 1.0

    def test_one_year_zero_profitable(self) -> None:
        result = diversity_score(_ONE_YEAR_ZERO_PROFITABLE)
        assert result["diversity_distinct_years"] == 1
        assert result["diversity_years_positive"] == 0
        assert result["diversity_score"] == 0.0

    def test_empty_breakdown(self) -> None:
        result = diversity_score([])
        assert result["diversity_score"] == 0.0
        assert result["diversity_distinct_years"] == 0
        assert result["diversity_years_positive"] == 0

    def test_keys_present(self) -> None:
        result = diversity_score(_THREE_YEAR_BREAKDOWN)
        assert set(result.keys()) == {
            "diversity_score",
            "diversity_distinct_years",
            "diversity_years_positive",
        }


# ---------------------------------------------------------------------------
# AC2: report() prints diversity block
# ---------------------------------------------------------------------------


class TestReportDiversityBlock:
    def test_diversity_block_printed_when_trades_provided(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        trades = _make_trades_df([2022, 2023, 2024], [1000.0, 2000.0, 500.0])
        results = _make_results_df()
        bh = {"sharpe": 0.5, "return": 0.10, "max_drawdown": -0.15, "calmar": 0.5}
        metadata = {"symbol": "CL", "freq": "1H"}

        with patch("research.experiments.evaluator._record_passing"):
            report(results, bh, metadata, trades_df=trades)

        captured = capsys.readouterr()
        assert "Regime Diversity" in captured.out
        assert "Score:" in captured.out
        assert "Years traded:" in captured.out
        assert "Profitable years:" in captured.out

    def test_no_diversity_block_without_trades(self, capsys: pytest.CaptureFixture[str]) -> None:
        results = _make_results_df()
        bh = {"sharpe": 0.5, "return": 0.10, "max_drawdown": -0.15, "calmar": 0.5}
        metadata = {"symbol": "CL", "freq": "1H"}

        with patch("research.experiments.evaluator._record_passing"):
            ret = report(results, bh, metadata)

        captured = capsys.readouterr()
        assert "Regime Diversity" not in captured.out
        assert ret is None


# ---------------------------------------------------------------------------
# AC3: warning fires when distinct_years < 3 OR profitable_years < 2
# ---------------------------------------------------------------------------


class TestDiversityWarnings:
    def test_warn_when_distinct_years_lt_3(self) -> None:
        # 2 distinct years → WARN
        output = _annual_breakdown(_make_trades_df([2023, 2024], [2000.0, 1500.0]))
        assert "[WARN] Diversity: only 2 year" in output

    def test_warn_when_profitable_years_lt_2(self) -> None:
        # 3 distinct but only 1 profitable
        trades = _make_trades_df([2022, 2023, 2024], [-100.0, -200.0, 3000.0])
        output = _annual_breakdown(trades)
        assert "[WARN] Diversity: only 1 profitable year" in output

    def test_both_warns_fire_when_one_year(self) -> None:
        trades = _make_trades_df([2024], [1000.0])
        output = _annual_breakdown(trades)
        # 1 distinct year → warn on distinct_years < 3
        assert "[WARN] Diversity:" in output

    def test_warn_fired_zero_profitable(self) -> None:
        trades = _make_trades_df([2022, 2023, 2024], [-100.0, -200.0, -50.0])
        output = _annual_breakdown(trades)
        assert "[WARN] Diversity: only 0 profitable year" in output


# ---------------------------------------------------------------------------
# AC4: warning silent when both thresholds met
# ---------------------------------------------------------------------------


class TestDiversityNoWarnAtThreshold:
    def test_no_warn_three_years_two_profitable(self) -> None:
        # 3 distinct, 2 profitable — exactly at thresholds — no warn
        trades = _make_trades_df([2022, 2023, 2024], [1000.0, 2000.0, -100.0])
        output = _annual_breakdown(trades)
        # distinct_years == 3 (not < 3), profitable == 2 (not < 2) → no warn
        assert "[WARN] Diversity:" not in output

    def test_no_warn_four_years_three_profitable(self) -> None:
        trades = _make_trades_df([2021, 2022, 2023, 2024], [500.0, 1000.0, 2000.0, -200.0])
        output = _annual_breakdown(trades)
        assert "[WARN] Diversity:" not in output


# ---------------------------------------------------------------------------
# AC5: qw record --bundle prints diversity warning when below threshold
# ---------------------------------------------------------------------------


class TestBundleCliDiversityWarning:
    """Verifying _cmd_bundle reads diversity from bundle.json trial_metadata and prints warning."""

    def _make_bundle_with_diversity(self, tmp_path: Path, diversity: dict[str, str]) -> None:
        manifest = {
            "trial": "test_trial",
            "run_ts": "20260416-120000",
            "files": {"csv": "baseline_results.csv", "csv_kind": "baseline_csv"},
            "trial_metadata": diversity,
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "40,0.60,1.5,2.5,-0.12,"
            "2024-01-02T10:00:00Z,2025-06-01T16:00:00Z\n"
        )
        (tmp_path / "baseline_results.csv").write_text(csv_content)

    def test_bundle_reads_diversity_fields_no_recompute(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """_cmd_bundle reads pre-computed diversity from bundle.json, writes to trial_metadata."""
        import argparse
        from unittest.mock import patch

        from research.graph.cli import _cmd_bundle
        from research.graph.store import GraphStore

        diversity = {
            "diversity_score": "0.3333",
            "diversity_distinct_years": "3",
            "diversity_years_positive": "1",
        }
        self._make_bundle_with_diversity(tmp_path, diversity)

        mock_store = MagicMock(spec=GraphStore)
        outcomes = [
            MagicMock(
                run_id="aaa000000001", status="recorded", evidence_score=2.5, champion_id=None
            )
        ]
        mock_store.persist_artifact.return_value = MagicMock(evolution=outcomes)

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=None,
            regime=None,
            rationale=None,
        )
        with (
            patch("research.graph.cli.NeoConnector") as mock_conn,
            patch("research.graph.cli.GraphStore.from_env", return_value=mock_store),
        ):
            mock_conn.return_value.is_available.return_value = True
            rc = _cmd_bundle(args)

        assert rc == 0
        # write_trial_metadata called with the diversity fields in trial_metadata
        mock_store.write_trial_metadata.assert_called_once()
        call_args = mock_store.write_trial_metadata.call_args[0]
        tm = call_args[1]
        assert "diversity_score" in tm
        assert "diversity_distinct_years" in tm
        assert "diversity_years_positive" in tm


# ---------------------------------------------------------------------------
# AC6: bundle.json includes diversity fields after evaluator writes them
# ---------------------------------------------------------------------------


class TestEvaluatorWritesToBundle:
    def test_diversity_written_to_bundle_json(self, tmp_path: Path) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps({"trial": "test", "files": {}}))

        trades = _make_trades_df([2022, 2023, 2024], [1000.0, 2000.0, 500.0])
        results = _make_results_df()
        bh = {"sharpe": 0.5, "return": 0.10, "max_drawdown": -0.15, "calmar": 0.5}
        metadata = {"symbol": "CL", "freq": "1H"}

        with patch("research.experiments.evaluator._record_passing"):
            div = report(results, bh, metadata, trades_df=trades, bundle_path=bundle_path)

        assert div is not None
        manifest = json.loads(bundle_path.read_text())
        tm = manifest.get("trial_metadata", {})
        assert "diversity_score" in tm
        assert "diversity_distinct_years" in tm
        assert "diversity_years_positive" in tm

    def test_diversity_merges_with_existing_trial_metadata(self, tmp_path: Path) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "trial": "test",
                    "files": {},
                    "trial_metadata": {"atr_bucket": "high"},
                }
            )
        )

        trades = _make_trades_df([2022, 2023, 2024], [1000.0, 2000.0, 500.0])
        results = _make_results_df()
        bh = {"sharpe": 0.5, "return": 0.10, "max_drawdown": -0.15, "calmar": 0.5}
        metadata = {"symbol": "CL", "freq": "1H"}

        with patch("research.experiments.evaluator._record_passing"):
            report(results, bh, metadata, trades_df=trades, bundle_path=bundle_path)

        manifest = json.loads(bundle_path.read_text())
        tm = manifest.get("trial_metadata", {})
        # existing key preserved
        assert tm.get("atr_bucket") == "high"
        # diversity keys added
        assert "diversity_score" in tm


# ---------------------------------------------------------------------------
# AC7: _cmd_bundle reads from bundle.json (does not recompute)
# ---------------------------------------------------------------------------


class TestBundleDoesNotRecompute:
    def test_trial_metadata_passed_as_is_to_write_trial_metadata(self, tmp_path: Path) -> None:
        """Verifies _cmd_bundle passes bundle.json trial_metadata directly."""
        import argparse
        from unittest.mock import patch

        from research.graph.cli import _cmd_bundle
        from research.graph.store import GraphStore

        manifest = {
            "trial": "test",
            "run_ts": "20260416-120000",
            "files": {"csv": "baseline_results.csv", "csv_kind": "baseline_csv"},
            "trial_metadata": {
                "diversity_score": "0.6667",
                "diversity_distinct_years": "3",
                "diversity_years_positive": "2",
                "atr_bucket": "low",
            },
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "40,0.60,1.5,2.5,-0.12,"
            "2024-01-02T10:00:00Z,2025-06-01T16:00:00Z\n"
        )
        (tmp_path / "baseline_results.csv").write_text(csv_content)

        mock_store = MagicMock(spec=GraphStore)
        outcomes = [
            MagicMock(
                run_id="aaa000000001", status="recorded", evidence_score=2.5, champion_id=None
            )
        ]
        mock_store.persist_artifact.return_value = MagicMock(evolution=outcomes)

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=None,
            regime=None,
            rationale=None,
        )
        with (
            patch("research.graph.cli.NeoConnector") as mock_conn,
            patch("research.graph.cli.GraphStore.from_env", return_value=mock_store),
        ):
            mock_conn.return_value.is_available.return_value = True
            rc = _cmd_bundle(args)

        assert rc == 0
        call_args = mock_store.write_trial_metadata.call_args[0]
        tm = call_args[1]
        # All four keys present — passed through from bundle.json
        assert tm["diversity_score"] == "0.6667"
        assert tm["diversity_distinct_years"] == "3"
        assert tm["diversity_years_positive"] == "2"
        assert tm["atr_bucket"] == "low"


# ---------------------------------------------------------------------------
# AC8: trial_metadata on Run node contains diversity keys after ingest
# ---------------------------------------------------------------------------


class TestTrialMetadataOnRunNode:
    def test_write_trial_metadata_called_with_diversity_keys(self, tmp_path: Path) -> None:
        """When bundle.json has diversity in trial_metadata, store.write_trial_metadata is called."""
        import argparse
        from unittest.mock import patch

        from research.graph.cli import _cmd_bundle
        from research.graph.store import GraphStore

        manifest = {
            "trial": "test",
            "run_ts": "20260416-120000",
            "files": {"csv": "baseline_results.csv", "csv_kind": "baseline_csv"},
            "trial_metadata": {
                "diversity_score": "0.6667",
                "diversity_distinct_years": "3",
                "diversity_years_positive": "2",
            },
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "40,0.60,1.5,2.5,-0.12,"
            "2024-01-02T10:00:00Z,2025-06-01T16:00:00Z\n"
        )
        (tmp_path / "baseline_results.csv").write_text(csv_content)

        mock_store = MagicMock(spec=GraphStore)
        outcomes = [
            MagicMock(
                run_id="aaa000000001", status="recorded", evidence_score=2.5, champion_id=None
            )
        ]
        mock_store.persist_artifact.return_value = MagicMock(evolution=outcomes)

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=None,
            regime=None,
            rationale=None,
        )
        with (
            patch("research.graph.cli.NeoConnector") as mock_conn,
            patch("research.graph.cli.GraphStore.from_env", return_value=mock_store),
        ):
            mock_conn.return_value.is_available.return_value = True
            _cmd_bundle(args)

        mock_store.write_trial_metadata.assert_called_once()
        call_args = mock_store.write_trial_metadata.call_args[0]
        assert call_args[0] == ["aaa000000001"]
        tm = call_args[1]
        assert "diversity_score" in tm
        assert "diversity_distinct_years" in tm
        assert "diversity_years_positive" in tm


# ---------------------------------------------------------------------------
# AC9: no auto-rejection — ingest proceeds regardless of diversity score
# ---------------------------------------------------------------------------


class TestNoAutoRejection:
    def test_ingest_proceeds_with_low_diversity(self, tmp_path: Path) -> None:
        """Ingest completes (rc=0) even when diversity is below both thresholds."""
        import argparse
        from unittest.mock import patch

        from research.graph.cli import _cmd_bundle
        from research.graph.store import GraphStore

        # diversity_distinct_years=1, diversity_years_positive=0 — worst possible
        manifest = {
            "trial": "test",
            "run_ts": "20260416-120000",
            "files": {"csv": "baseline_results.csv", "csv_kind": "baseline_csv"},
            "trial_metadata": {
                "diversity_score": "0.0",
                "diversity_distinct_years": "1",
                "diversity_years_positive": "0",
            },
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "40,0.60,1.5,2.5,-0.12,"
            "2024-01-02T10:00:00Z,2025-06-01T16:00:00Z\n"
        )
        (tmp_path / "baseline_results.csv").write_text(csv_content)

        mock_store = MagicMock(spec=GraphStore)
        outcomes = [
            MagicMock(
                run_id="aaa000000001", status="recorded", evidence_score=2.5, champion_id=None
            )
        ]
        mock_store.persist_artifact.return_value = MagicMock(evolution=outcomes)

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=None,
            regime=None,
            rationale=None,
        )
        with (
            patch("research.graph.cli.NeoConnector") as mock_conn,
            patch("research.graph.cli.GraphStore.from_env", return_value=mock_store),
        ):
            mock_conn.return_value.is_available.return_value = True
            rc = _cmd_bundle(args)

        assert rc == 0  # ingest proceeded — no auto-rejection
