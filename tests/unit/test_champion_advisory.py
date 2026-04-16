# mypy: ignore-errors
"""Unit tests for QWS-1405 — champion degradation advisory.

Tests:
  - qw monitor --audit-lineage prints advisory for matching Champions
  - Advisory silent for non-matching Champions
  - --dry-run produces identical advisory output (no graph writes)
  - qw degrade --degrade-reason stores degrade_reason on FormerChampion
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# qws_graph lives at qws_graph/ relative to repo root — add to path
_QWS_GRAPH_ROOT = str(Path(__file__).resolve().parents[2] / "qws_graph")
if _QWS_GRAPH_ROOT not in sys.path:
    sys.path.insert(0, _QWS_GRAPH_ROOT)

from research.graph.cli import _cmd_monitor_audit_lineage, cmd_degrade, cmd_monitor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _monitor_args(
    audit_lineage: bool = False,
    dry_run: bool = False,
    champion_id: str | None = None,
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        audit_lineage=audit_lineage,
        dry_run=dry_run,
        champion_id=champion_id,
        repo_root=None,
        timeout_seconds=timeout_seconds,
    )


def _degrade_args(
    champion_id: str = "champ001",
    reason: str = "MaxDD breached",
    degrade_reason: str | None = None,
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        champion_id=champion_id,
        reason=reason,
        degrade_reason=degrade_reason,
        timeout_seconds=timeout_seconds,
    )


_MATCHING_ROW = {
    "champion_id": "abc123",
    "name": "cl-bear-sweep",
    "metrics_total_trades": 7,
    "oos_status": "oos_pending",
    "hypothesis_id": "hyp999",
    "hypothesis_status": "rejected",
}

_NON_MATCHING_ROW_CONFIRMED = {
    "champion_id": "def456",
    "name": "mes-trend",
    "metrics_total_trades": 7,
    "oos_status": "oos_pending",
    "hypothesis_id": "hyp888",
    "hypothesis_status": "confirmed",  # not rejected
}


# ---------------------------------------------------------------------------
# _cmd_monitor_audit_lineage tests
# ---------------------------------------------------------------------------


class TestAuditLineage:
    def _make_connector(self, timeout_seconds: int = 3) -> MagicMock:
        connector = MagicMock()
        connector.timeout_seconds = timeout_seconds
        return connector

    def test_advisory_fires_for_matching_champion(self, capsys) -> None:
        connector = self._make_connector()
        with patch("research.graph.store.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.run_adhoc_cypher.return_value = [_MATCHING_ROW]
            mock_from_env.return_value = mock_store

            rc = _cmd_monitor_audit_lineage(connector)

        assert rc == 0
        out = capsys.readouterr().out
        assert "ADVISORY:" in out
        assert "abc123" in out
        assert "cl-bear-sweep" in out
        assert "hyp999" in out
        assert "status=rejected" in out
        assert "oos_pending" in out
        assert "qw degrade abc123 --reason lineage_rejected" in out

    def test_advisory_silent_for_empty_results(self, capsys) -> None:
        connector = self._make_connector()
        with patch("research.graph.store.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.run_adhoc_cypher.return_value = []
            mock_from_env.return_value = mock_store

            rc = _cmd_monitor_audit_lineage(connector)

        assert rc == 0
        out = capsys.readouterr().out
        assert "ADVISORY" not in out

    def test_store_error_returns_nonzero(self, capsys) -> None:
        from research.graph.store import StoreInfraError

        connector = self._make_connector()
        with patch("research.graph.store.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.run_adhoc_cypher.side_effect = StoreInfraError("connection lost")
            mock_from_env.return_value = mock_store

            rc = _cmd_monitor_audit_lineage(connector)

        assert rc != 0


class TestCmdMonitorAuditLineage:
    def test_audit_lineage_flag_routes_to_audit_function(self, capsys) -> None:
        args = _monitor_args(audit_lineage=True)
        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector.timeout_seconds = 3
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.run_adhoc_cypher.return_value = [_MATCHING_ROW]
            mock_from_env.return_value = mock_store

            rc = cmd_monitor(args)

        assert rc == 0
        out = capsys.readouterr().out
        assert "ADVISORY:" in out

    def test_dry_run_with_audit_lineage_produces_same_output(self, capsys) -> None:
        """--dry-run + --audit-lineage: advisory output identical, no graph writes."""
        args_dry = _monitor_args(audit_lineage=True, dry_run=True)
        args_normal = _monitor_args(audit_lineage=True, dry_run=False)

        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector.timeout_seconds = 3
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.run_adhoc_cypher.return_value = [_MATCHING_ROW]
            mock_from_env.return_value = mock_store

            rc_dry = cmd_monitor(args_dry)
            out_dry = capsys.readouterr().out

            mock_store.run_adhoc_cypher.return_value = [_MATCHING_ROW]
            rc_normal = cmd_monitor(args_normal)
            out_normal = capsys.readouterr().out

        assert rc_dry == 0
        assert rc_normal == 0
        assert out_dry == out_normal
        # advisory mode never writes — store.degrade_champion not called
        mock_store.degrade_champion.assert_not_called()

    def test_no_audit_lineage_flag_runs_normal_monitor(self) -> None:
        args = _monitor_args(audit_lineage=False)
        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.cli.MonitorRunner") as mock_runner_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_runner = MagicMock()
            mock_runner.run.return_value = []
            mock_runner_cls.return_value = mock_runner

            rc = cmd_monitor(args)

        assert rc == 0
        mock_runner.run.assert_called_once()


# ---------------------------------------------------------------------------
# qw degrade --degrade-reason tests
# ---------------------------------------------------------------------------


class TestCmdDegradeReason:
    def test_degrade_reason_passed_to_store(self) -> None:
        args = _degrade_args(degrade_reason="lineage_rejected")
        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.return_value = "fc_new001"
            mock_from_env.return_value = mock_store

            rc = cmd_degrade(args)

        assert rc == 0
        mock_store.degrade_champion.assert_called_once_with(
            champion_id="champ001",
            oos_reason="MaxDD breached",
            degrade_reason="lineage_rejected",
        )

    def test_degrade_without_degrade_reason_omits_kwarg(self) -> None:
        """When degrade_reason is None, the kwarg is omitted from the store call."""
        args = _degrade_args(degrade_reason=None)
        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.return_value = "fc_new002"
            mock_from_env.return_value = mock_store

            rc = cmd_degrade(args)

        assert rc == 0
        # degrade_reason kwarg omitted when None
        mock_store.degrade_champion.assert_called_once_with(
            champion_id="champ001",
            oos_reason="MaxDD breached",
        )

    def test_empty_degrade_reason_omits_kwarg(self) -> None:
        """Whitespace degrade_reason is treated as absent — kwarg omitted."""
        args = _degrade_args(degrade_reason="   ")
        with (
            patch("research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.return_value = "fc_new003"
            mock_from_env.return_value = mock_store

            rc = cmd_degrade(args)

        assert rc == 0
        mock_store.degrade_champion.assert_called_once_with(
            champion_id="champ001",
            oos_reason="MaxDD breached",
        )
