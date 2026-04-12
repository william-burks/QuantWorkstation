"""Unit tests for qw degrade and qw retire CLI commands (QWS-0801)."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.cli import cmd_degrade, cmd_retire


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _degrade_args(
    champion_id: str = "champ123",
    reason: str | None = "MaxDD breached -15%",
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        champion_id=champion_id,
        reason=reason,
        timeout_seconds=timeout_seconds,
    )


def _retire_args(
    former_champion_id: str = "fc_001",
    note: str | None = "No pivot found",
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        former_champion_id=former_champion_id,
        note=note,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# qw degrade tests
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_missing_reason_exits_nonzero(self) -> None:
        args = _degrade_args(reason=None)
        # argparse with required=True would reject this, but test the function directly
        rc = cmd_degrade(args)
        assert rc != 0

    def test_empty_reason_exits_nonzero(self) -> None:
        args = _degrade_args(reason="")
        rc = cmd_degrade(args)
        assert rc != 0

    def test_whitespace_reason_exits_nonzero(self) -> None:
        args = _degrade_args(reason="   ")
        rc = cmd_degrade(args)
        assert rc != 0

    def test_valid_degrade_exits_zero(self) -> None:
        args = _degrade_args()
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.return_value = "fc_abc123"
            mock_from_env.return_value = mock_store

            rc = cmd_degrade(args)
            assert rc == 0
            mock_store.degrade_champion.assert_called_once_with(
                champion_id="champ123",
                oos_reason="MaxDD breached -15%",
            )

    def test_neo4j_unavailable_exits_nonzero(self) -> None:
        args = _degrade_args()
        with patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = False
            mock_connector_cls.return_value = mock_connector
            rc = cmd_degrade(args)
            assert rc != 0

    def test_non_existent_champion_exits_nonzero(self) -> None:
        args = _degrade_args(champion_id="ghost_id")
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.side_effect = ValueError("Champion 'ghost_id' not found")
            mock_from_env.return_value = mock_store

            rc = cmd_degrade(args)
            assert rc != 0


# ---------------------------------------------------------------------------
# qw retire tests
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_valid_retire_with_note_exits_zero(self) -> None:
        args = _retire_args()
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "rc_new_001"
            mock_from_env.return_value = mock_store

            rc = cmd_retire(args)
            assert rc == 0
            mock_store.retire_former_champion.assert_called_once_with(
                former_champion_id="fc_001",
                retirement_note="No pivot found",
            )

    def test_retire_without_note_exits_zero(self) -> None:
        args = _retire_args(note=None)
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "rc_new_002"
            mock_from_env.return_value = mock_store

            rc = cmd_retire(args)
            assert rc == 0
            mock_store.retire_former_champion.assert_called_once_with(
                former_champion_id="fc_001",
                retirement_note=None,
            )

    def test_neo4j_unavailable_exits_nonzero(self) -> None:
        args = _retire_args()
        with patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = False
            mock_connector_cls.return_value = mock_connector
            rc = cmd_retire(args)
            assert rc != 0

    def test_non_existent_former_champion_exits_nonzero(self) -> None:
        args = _retire_args(former_champion_id="ghost_fc")
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.store.GraphStore.from_env") as mock_from_env,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.side_effect = ValueError(
                "FormerChampion 'ghost_fc' not found"
            )
            mock_from_env.return_value = mock_store

            rc = cmd_retire(args)
            assert rc != 0
