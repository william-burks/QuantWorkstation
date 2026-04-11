"""Unit tests for qw degrade / qw retire CLI commands (QWS-0801).

Tests: cmd_degrade(), cmd_retire() argument parsing and exit codes.
Uses mocked GraphStore and NeoConnector — no live Neo4j required.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.cli import cmd_degrade, cmd_retire
from qws_graph.research.graph.store import StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _degrade_args(
    champion: str = "demo_champ_001",
    reason: str = "OOS fail — MaxDD breach",
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        champion=champion,
        reason=reason,
        timeout_seconds=timeout_seconds,
    )


def _retire_args(
    former_champion: str = "fc_abc123def456",
    note: str | None = None,
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        former_champion=former_champion,
        note=note,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# cmd_degrade
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_valid_degrade_exits_0(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.return_value = "abc123def456"
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_degrade(_degrade_args())
            assert rc == 0

    def test_missing_reason_exits_1(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            rc = cmd_degrade(_degrade_args(reason=""))
            assert rc == 1

    def test_empty_reason_exits_1(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            rc = cmd_degrade(_degrade_args(reason="   "))
            assert rc == 1

    def test_nonexistent_champion_exits_1(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.side_effect = StoreError("Champion 'x' not found in graph")
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_degrade(_degrade_args(champion="nonexistent_id"))
            assert rc == 1

    def test_neo4j_unavailable_exits_2(self) -> None:
        with patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = False
            mock_connector_cls.return_value = mock_connector

            rc = cmd_degrade(_degrade_args())
            assert rc == 2

    def test_infra_error_exits_2(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.degrade_champion.side_effect = StoreInfraError("bolt://localhost unreachable")
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_degrade(_degrade_args())
            assert rc == 2


# ---------------------------------------------------------------------------
# cmd_retire
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_valid_retire_with_note_exits_0(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "abc123def456"
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_retire(_retire_args(note="Logic dead-ended"))
            assert rc == 0

    def test_retire_without_note_exits_0(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "abc123def456"
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_retire(_retire_args(note=None))
            assert rc == 0

    def test_nonexistent_former_champion_exits_1(self) -> None:
        with (
            patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls,
            patch("qws_graph.research.graph.cli.GraphStore") as mock_store_cls,
        ):
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = True
            mock_connector_cls.return_value = mock_connector

            mock_store = MagicMock()
            mock_store.retire_former_champion.side_effect = StoreError("FormerChampion 'x' not found")
            mock_store_cls.from_env.return_value = mock_store

            rc = cmd_retire(_retire_args(former_champion="nonexistent_fc"))
            assert rc == 1

    def test_neo4j_unavailable_exits_2(self) -> None:
        with patch("qws_graph.research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector = MagicMock()
            mock_connector.is_available.return_value = False
            mock_connector_cls.return_value = mock_connector

            rc = cmd_retire(_retire_args())
            assert rc == 2
