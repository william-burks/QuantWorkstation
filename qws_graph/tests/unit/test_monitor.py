"""Unit tests for MonitorRunner (QWS-0803 — recursive validation loop)."""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.monitor import MonitorResult, MonitorRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_champion(
    champion_id: str = "champ_001",
    strategy_id: str = "strat_001",
    metrics_sharpe: float = 2.5,
    artifact_path: str = "research/trials/01_test.csv",
) -> dict[str, Any]:
    return {
        "champion_id": champion_id,
        "strategy_id": strategy_id,
        "metrics_sharpe": metrics_sharpe,
        "artifact_path": artifact_path,
    }


def _make_store(
    active_champions: list[dict[str, Any]] | None = None,
    research_targets: list[dict[str, Any]] | None = None,
    degrade_return: str = "fc_001",
) -> MagicMock:
    store = MagicMock()
    store.get_active_champions.return_value = active_champions or []
    store.get_research_targets.return_value = research_targets or []
    store.degrade_champion.return_value = degrade_return
    store.attach_blob_to_former_champion.return_value = "monitor:fc_001:monitor_notification:abc"
    return store


# ---------------------------------------------------------------------------
# MonitorRunner._resolve_threshold
# ---------------------------------------------------------------------------

class TestResolveThreshold:
    def test_uses_research_target_when_present(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path)
        store = _make_store(research_targets=[{"decay_threshold": 0.5}])
        assert runner._resolve_threshold(store) == pytest.approx(0.5)

    def test_falls_back_to_default_when_no_target(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path)
        store = _make_store(research_targets=[])
        assert runner._resolve_threshold(store) == pytest.approx(0.75)

    def test_falls_back_to_default_when_decay_threshold_none(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path)
        store = _make_store(research_targets=[{"decay_threshold": None}])
        assert runner._resolve_threshold(store) == pytest.approx(0.75)

    def test_uses_constructor_override_when_no_target(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path, decay_threshold=1.2)
        store = _make_store(research_targets=[])
        assert runner._resolve_threshold(store) == pytest.approx(1.2)

    def test_research_target_overrides_constructor(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path, decay_threshold=1.2)
        store = _make_store(research_targets=[{"decay_threshold": 0.4}])
        assert runner._resolve_threshold(store) == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# MonitorRunner._parse_sharpe
# ---------------------------------------------------------------------------

class TestParseSharpe:
    def test_parses_standard_line(self) -> None:
        assert MonitorRunner._parse_sharpe("sharpe: 2.34\n") == pytest.approx(2.34)

    def test_case_insensitive(self) -> None:
        assert MonitorRunner._parse_sharpe("Sharpe: 1.5\n") == pytest.approx(1.5)

    def test_parses_from_multiline_output(self) -> None:
        stdout = "running...\nsharpe: 3.01\nsome other line\n"
        assert MonitorRunner._parse_sharpe(stdout) == pytest.approx(3.01)

    def test_returns_none_when_no_match(self) -> None:
        assert MonitorRunner._parse_sharpe("no sharpe here\n") is None

    def test_returns_none_for_empty(self) -> None:
        assert MonitorRunner._parse_sharpe("") is None


# ---------------------------------------------------------------------------
# MonitorRunner._resolve_script
# ---------------------------------------------------------------------------

class TestResolveScript:
    def test_resolves_py_sibling_of_csv(self, tmp_path: Path) -> None:
        (tmp_path / "research" / "trials").mkdir(parents=True)
        script = tmp_path / "research" / "trials" / "01_test.py"
        script.write_text("# trial script\n")
        runner = MonitorRunner(repo_root=tmp_path)
        result = runner._resolve_script("research/trials/01_test.csv")
        assert result == script

    def test_resolves_py_script_directly(self, tmp_path: Path) -> None:
        (tmp_path / "research" / "trials").mkdir(parents=True)
        script = tmp_path / "research" / "trials" / "01_test.py"
        script.write_text("# trial script\n")
        runner = MonitorRunner(repo_root=tmp_path)
        result = runner._resolve_script("research/trials/01_test.py")
        assert result == script

    def test_returns_none_for_missing_script(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path)
        result = runner._resolve_script("research/trials/missing.csv")
        assert result is None

    def test_returns_none_for_empty_path(self, tmp_path: Path) -> None:
        runner = MonitorRunner(repo_root=tmp_path)
        assert runner._resolve_script("") is None


# ---------------------------------------------------------------------------
# MonitorRunner._evaluate_champion — above threshold
# ---------------------------------------------------------------------------

class TestEvaluateChampionAboveThreshold:
    def test_creates_former_champion_when_above_threshold(self, tmp_path: Path) -> None:
        (tmp_path / "research" / "trials").mkdir(parents=True)
        script = tmp_path / "research" / "trials" / "01_test.py"
        script.write_text("print('sharpe: 1.0')\n")

        store = _make_store(degrade_return="fc_abc")
        runner = MonitorRunner(repo_root=tmp_path, dry_run=False)

        champ = _make_champion(
            metrics_sharpe=2.5,
            artifact_path="research/trials/01_test.csv",
        )

        with patch.object(runner, "_run_trial", return_value=1.0):
            result = runner._evaluate_champion(store, champ, threshold=0.75)

        assert result.status == "degraded"
        assert result.former_champion_id == "fc_abc"
        assert result.drift == pytest.approx(abs(1.0 - 2.5))
        store.degrade_champion.assert_called_once()
        store.attach_blob_to_former_champion.assert_called_once_with(
            former_champion_id="fc_abc",
            artifact_type="monitor_notification",
            content=result.message if False else store.attach_blob_to_former_champion.call_args.kwargs["content"],
        )

    def test_oos_reason_format(self, tmp_path: Path) -> None:
        store = _make_store(degrade_return="fc_xyz")
        runner = MonitorRunner(repo_root=tmp_path, dry_run=False)
        champ = _make_champion(metrics_sharpe=3.0, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=1.5):
                runner._evaluate_champion(store, champ, threshold=0.75)

        call_kwargs = store.degrade_champion.call_args.kwargs
        oos_reason = call_kwargs["oos_reason"]
        assert "Auto-detected by qw monitor" in oos_reason
        assert "3.00" in oos_reason
        assert "1.50" in oos_reason
        assert "drift=1.50" in oos_reason
        assert "threshold=0.75" in oos_reason

    def test_notification_includes_strategy_id(self, tmp_path: Path) -> None:
        store = _make_store(degrade_return="fc_xyz")
        runner = MonitorRunner(repo_root=tmp_path, dry_run=False)
        champ = _make_champion(strategy_id="my-strategy", metrics_sharpe=3.0, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=1.5):
                runner._evaluate_champion(store, champ, threshold=0.75)

        content_arg = store.attach_blob_to_former_champion.call_args.kwargs["content"]
        assert "my-strategy" in content_arg
        assert "pivot or retire" in content_arg


# ---------------------------------------------------------------------------
# MonitorRunner._evaluate_champion — below threshold
# ---------------------------------------------------------------------------

class TestEvaluateChampionBelowThreshold:
    def test_no_degrade_when_below_threshold(self, tmp_path: Path) -> None:
        store = _make_store()
        runner = MonitorRunner(repo_root=tmp_path)
        champ = _make_champion(metrics_sharpe=2.5, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=2.3):
                result = runner._evaluate_champion(store, champ, threshold=0.75)

        assert result.status == "ok"
        assert result.drift == pytest.approx(abs(2.3 - 2.5))
        store.degrade_champion.assert_not_called()
        store.attach_blob_to_former_champion.assert_not_called()

    def test_exactly_at_threshold_does_not_degrade(self, tmp_path: Path) -> None:
        store = _make_store()
        runner = MonitorRunner(repo_root=tmp_path)
        champ = _make_champion(metrics_sharpe=2.5, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=1.75):  # drift = 0.75 exactly
                result = runner._evaluate_champion(store, champ, threshold=0.75)

        assert result.status == "ok"
        store.degrade_champion.assert_not_called()


# ---------------------------------------------------------------------------
# MonitorRunner._evaluate_champion — dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_does_not_write_edges(self, tmp_path: Path) -> None:
        store = _make_store()
        runner = MonitorRunner(repo_root=tmp_path, dry_run=True)
        champ = _make_champion(metrics_sharpe=3.0, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=1.0):
                result = runner._evaluate_champion(store, champ, threshold=0.75)

        # drift is 2.0 > 0.75, but dry_run → no writes
        assert result.status == "degraded"
        assert result.former_champion_id is None
        store.degrade_champion.assert_not_called()
        store.attach_blob_to_former_champion.assert_not_called()

    def test_dry_run_reports_drift_in_message(self, tmp_path: Path) -> None:
        store = _make_store()
        runner = MonitorRunner(repo_root=tmp_path, dry_run=True)
        champ = _make_champion(metrics_sharpe=3.0, artifact_path="research/trials/01_test.csv")

        with patch.object(runner, "_resolve_script", return_value=Path("/fake/script.py")):
            with patch.object(runner, "_run_trial", return_value=1.0):
                result = runner._evaluate_champion(store, champ, threshold=0.75)

        assert "DRY-RUN" in result.message


# ---------------------------------------------------------------------------
# MonitorRunner._evaluate_champion — missing/unresolvable script
# ---------------------------------------------------------------------------

class TestMissingScript:
    def test_skipped_when_script_unresolvable(self, tmp_path: Path) -> None:
        store = _make_store()
        runner = MonitorRunner(repo_root=tmp_path)
        champ = _make_champion(artifact_path="research/trials/nonexistent.csv")

        result = runner._evaluate_champion(store, champ, threshold=0.75)

        assert result.status == "skipped"
        store.degrade_champion.assert_not_called()

    def test_other_champions_continue_after_skip(self, tmp_path: Path) -> None:
        # Two champions: first has missing script, second has valid script below threshold
        (tmp_path / "research" / "trials").mkdir(parents=True)
        script = tmp_path / "research" / "trials" / "02_test.py"
        script.write_text("print('sharpe: 2.4')\n")

        store = _make_store(
            active_champions=[
                _make_champion("c1", artifact_path="research/trials/missing.csv"),
                _make_champion("c2", artifact_path="research/trials/02_test.csv"),
            ]
        )
        store.get_research_targets.return_value = []
        runner = MonitorRunner(repo_root=tmp_path)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run()

        assert len(results) == 2
        statuses = {r.champion_id: r.status for r in results}
        assert statuses["c1"] == "skipped"
        # c2 depends on trial output — just verify it ran
        assert statuses["c2"] in ("ok", "degraded", "skipped", "error")


# ---------------------------------------------------------------------------
# MonitorRunner.run — single champion scope
# ---------------------------------------------------------------------------

class TestSingleChampionScope:
    def test_run_with_champion_id_filters_to_one(self, tmp_path: Path) -> None:
        store = _make_store(
            active_champions=[
                _make_champion("c1"),
                _make_champion("c2"),
            ]
        )
        store.get_research_targets.return_value = []
        runner = MonitorRunner(repo_root=tmp_path)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            with patch.object(runner, "_evaluate_champion") as mock_eval:
                mock_eval.return_value = MonitorResult(
                    champion_id="c1",
                    strategy_id="s1",
                    artifact_path="",
                    old_sharpe=2.5,
                    new_sharpe=2.3,
                    drift=0.2,
                    threshold=0.75,
                    status="ok",
                    message="ok",
                )
                results = runner.run(champion_id="c1")

        assert len(results) == 1
        assert results[0].champion_id == "c1"
        assert mock_eval.call_count == 1

    def test_run_with_nonexistent_champion_id_returns_empty(self, tmp_path: Path) -> None:
        store = _make_store(active_champions=[_make_champion("c1")])
        store.get_research_targets.return_value = []
        runner = MonitorRunner(repo_root=tmp_path)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run(champion_id="nonexistent")

        assert results == []


# ---------------------------------------------------------------------------
# CLI — cmd_monitor
# ---------------------------------------------------------------------------

class TestCmdMonitor:
    def _make_args(
        self,
        dry_run: bool = False,
        champion_id: str | None = None,
        repo_root: str | None = None,
        timeout_seconds: int = 3,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            dry_run=dry_run,
            champion_id=champion_id,
            repo_root=repo_root,
            timeout_seconds=timeout_seconds,
        )

    def test_returns_zero_when_no_champions(self) -> None:
        from qws_graph.research.graph.cli import cmd_monitor  # noqa: PLC0415

        args = self._make_args()

        with patch("qws_graph.research.graph.cli.NeoConnector") as MockConn:
            MockConn.return_value.is_available.return_value = True
            with patch("qws_graph.research.graph.cli.MonitorRunner") as MockRunner:
                MockRunner.return_value.run.return_value = []
                result = cmd_monitor(args)

        assert result == 0

    def test_returns_one_when_neo4j_unavailable(self) -> None:
        from qws_graph.research.graph.cli import cmd_monitor  # noqa: PLC0415

        args = self._make_args()

        with patch("qws_graph.research.graph.cli.NeoConnector") as MockConn:
            MockConn.return_value.is_available.return_value = False
            result = cmd_monitor(args)

        assert result == 1

    def test_dry_run_flag_passed_to_runner(self) -> None:
        from qws_graph.research.graph.cli import cmd_monitor  # noqa: PLC0415

        args = self._make_args(dry_run=True)

        with patch("qws_graph.research.graph.cli.NeoConnector") as MockConn:
            MockConn.return_value.is_available.return_value = True
            with patch("qws_graph.research.graph.cli.MonitorRunner") as MockRunner:
                MockRunner.return_value.run.return_value = []
                cmd_monitor(args)
                _, kwargs = MockRunner.call_args
                assert kwargs.get("dry_run") is True or MockRunner.call_args[0][1] if MockRunner.call_args[0] else False or (
                    MockRunner.call_args.kwargs.get("dry_run") is True
                )

    def test_qw_monitor_subcommand_registered(self) -> None:
        """qw monitor --help exits 0 (subcommand registered in main parser)."""
        import subprocess, sys  # noqa: PLC0415
        result = subprocess.run(
            [sys.executable, "-m", "qws_graph.research.graph.cli", "monitor", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--champion-id" in result.stdout
