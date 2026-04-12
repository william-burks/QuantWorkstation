"""Integration test — MonitorRunner end-to-end with mock trial script (QWS-0803).

Uses a temporary Python script that outputs ``sharpe: <float>`` to stdout.
Runs against a mock store (no live Neo4j required).
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.monitor import MonitorRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def trial_script_below_threshold(tmp_path: Path) -> tuple[Path, Path]:
    """Create a trial script that outputs sharpe within threshold of 2.5."""
    script_dir = tmp_path / "research" / "trials"
    script_dir.mkdir(parents=True)
    script = script_dir / "01_stable.py"
    script.write_text(textwrap.dedent("""\
        import sys
        print("sharpe: 2.45")
        sys.exit(0)
    """))
    return tmp_path, script


@pytest.fixture()
def trial_script_above_threshold(tmp_path: Path) -> tuple[Path, Path]:
    """Create a trial script that outputs sharpe above threshold of 2.5 by > 0.75."""
    script_dir = tmp_path / "research" / "trials"
    script_dir.mkdir(parents=True)
    script = script_dir / "02_degraded.py"
    script.write_text(textwrap.dedent("""\
        import sys
        print("sharpe: 1.0")
        sys.exit(0)
    """))
    return tmp_path, script


def _make_store_for_integration(
    active_champions: list[dict],
    degrade_return: str = "fc_integration_001",
) -> MagicMock:
    store = MagicMock()
    store.get_active_champions.return_value = active_champions
    store.get_research_targets.return_value = []
    store.degrade_champion.return_value = degrade_return
    store.attach_blob_to_former_champion.return_value = (
        "monitor:fc_integration_001:monitor_notification:test"
    )
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMonitorEndToEnd:
    def test_below_threshold_no_degrade(
        self, trial_script_below_threshold: tuple[Path, Path]
    ) -> None:
        repo_root, script = trial_script_below_threshold
        artifact_path = str(script.relative_to(repo_root).with_suffix(".csv"))

        champion = {
            "champion_id": "c_stable",
            "strategy_id": "strat_stable",
            "metrics_sharpe": 2.5,
            "artifact_path": artifact_path,
        }
        store = _make_store_for_integration([champion])

        runner = MonitorRunner(repo_root=repo_root)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run()

        assert len(results) == 1
        result = results[0]
        assert result.status == "ok"
        assert result.drift is not None
        assert result.drift < 0.75
        store.degrade_champion.assert_not_called()
        store.attach_blob_to_former_champion.assert_not_called()

    def test_above_threshold_creates_degrade(
        self, trial_script_above_threshold: tuple[Path, Path]
    ) -> None:
        repo_root, script = trial_script_above_threshold
        artifact_path = str(script.relative_to(repo_root).with_suffix(".csv"))

        champion = {
            "champion_id": "c_degraded",
            "strategy_id": "strat_degraded",
            "metrics_sharpe": 2.5,
            "artifact_path": artifact_path,
        }
        store = _make_store_for_integration([champion])

        runner = MonitorRunner(repo_root=repo_root)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run()

        assert len(results) == 1
        result = results[0]
        assert result.status == "degraded"
        assert result.former_champion_id == "fc_integration_001"
        assert result.drift is not None
        assert result.drift > 0.75

        store.degrade_champion.assert_called_once()
        call_kwargs = store.degrade_champion.call_args.kwargs
        assert call_kwargs["champion_id"] == "c_degraded"
        assert "Auto-detected by qw monitor" in call_kwargs["oos_reason"]
        assert "2.50" in call_kwargs["oos_reason"]
        assert "1.00" in call_kwargs["oos_reason"]

        store.attach_blob_to_former_champion.assert_called_once_with(
            former_champion_id="fc_integration_001",
            artifact_type="monitor_notification",
            content=store.attach_blob_to_former_champion.call_args.kwargs["content"],
        )
        notification_content = store.attach_blob_to_former_champion.call_args.kwargs["content"]
        assert "strat_degraded" in notification_content
        assert "pivot or retire" in notification_content

    def test_dry_run_above_threshold_no_writes(
        self, trial_script_above_threshold: tuple[Path, Path]
    ) -> None:
        repo_root, script = trial_script_above_threshold
        artifact_path = str(script.relative_to(repo_root).with_suffix(".csv"))

        champion = {
            "champion_id": "c_dry",
            "strategy_id": "strat_dry",
            "metrics_sharpe": 2.5,
            "artifact_path": artifact_path,
        }
        store = _make_store_for_integration([champion])

        runner = MonitorRunner(repo_root=repo_root, dry_run=True)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run()

        assert len(results) == 1
        result = results[0]
        assert result.status == "degraded"
        assert result.former_champion_id is None
        store.degrade_champion.assert_not_called()
        store.attach_blob_to_former_champion.assert_not_called()

    def test_champion_id_filter_restricts_scope(
        self, trial_script_below_threshold: tuple[Path, Path]
    ) -> None:
        repo_root, script = trial_script_below_threshold
        artifact_path = str(script.relative_to(repo_root).with_suffix(".csv"))

        champions = [
            {
                "champion_id": "c_a",
                "strategy_id": "s_a",
                "metrics_sharpe": 2.5,
                "artifact_path": artifact_path,
            },
            {
                "champion_id": "c_b",
                "strategy_id": "s_b",
                "metrics_sharpe": 2.5,
                "artifact_path": artifact_path,
            },
        ]
        store = _make_store_for_integration(champions)

        runner = MonitorRunner(repo_root=repo_root)

        with patch("qws_graph.research.graph.monitor.GraphStore") as MockStore:
            MockStore.from_env.return_value = store
            results = runner.run(champion_id="c_a")

        assert len(results) == 1
        assert results[0].champion_id == "c_a"
