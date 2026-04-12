"""Unit tests for `qw degrade` and `qw retire` CLI commands (QWS-0801)."""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.cli import cmd_degrade, cmd_retire
from qws_graph.research.graph.store import StoreInfraError


def _degrade_args(
    champion_id: str = "champ_001",
    reason: str = "MaxDD breach",
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        champion_id=champion_id,
        reason=reason,
        timeout_seconds=timeout_seconds,
    )


def _retire_args(
    former_champion_id: str = "fc_001",
    note: str | None = "No pivot",
    timeout_seconds: int = 3,
) -> argparse.Namespace:
    return argparse.Namespace(
        former_champion_id=former_champion_id,
        note=note,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# cmd_degrade
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_valid_degrade_exits_zero(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.degrade_champion.return_value = "abc123def456"
        mock_store_cls.from_env.return_value = store

        rc = cmd_degrade(_degrade_args())
        assert rc == 0

    @patch("qws_graph.research.graph.cli.NeoConnector")
    def test_empty_reason_exits_one(self, mock_connector_cls: MagicMock) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        rc = cmd_degrade(_degrade_args(reason="  "))
        assert rc == 1

    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_champion_not_found_exits_one(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.degrade_champion.return_value = None
        mock_store_cls.from_env.return_value = store

        rc = cmd_degrade(_degrade_args(champion_id="nonexistent"))
        assert rc == 1

    @patch("qws_graph.research.graph.cli.NeoConnector")
    def test_neo4j_unavailable_exits_two(self, mock_connector_cls: MagicMock) -> None:
        mock_connector_cls.return_value.is_available.return_value = False
        rc = cmd_degrade(_degrade_args())
        assert rc == 2

    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_store_infra_error_exits_two(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.degrade_champion.side_effect = StoreInfraError("boom")
        mock_store_cls.from_env.return_value = store

        rc = cmd_degrade(_degrade_args())
        assert rc == 2


# ---------------------------------------------------------------------------
# cmd_retire
# ---------------------------------------------------------------------------


class TestCmdRetire:
    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_valid_retire_exits_zero(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.retire_former_champion.return_value = True
        mock_store_cls.from_env.return_value = store

        rc = cmd_retire(_retire_args())
        assert rc == 0

    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_retire_without_note_exits_zero(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.retire_former_champion.return_value = True
        mock_store_cls.from_env.return_value = store

        rc = cmd_retire(_retire_args(note=None))
        assert rc == 0

    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_former_champion_not_found_exits_one(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.retire_former_champion.return_value = False
        mock_store_cls.from_env.return_value = store

        rc = cmd_retire(_retire_args(former_champion_id="ghost_fc"))
        assert rc == 1

    @patch("qws_graph.research.graph.cli.NeoConnector")
    def test_neo4j_unavailable_exits_two(self, mock_connector_cls: MagicMock) -> None:
        mock_connector_cls.return_value.is_available.return_value = False
        rc = cmd_retire(_retire_args())
        assert rc == 2

    @patch("qws_graph.research.graph.cli.NeoConnector")
    @patch("qws_graph.research.graph.cli.GraphStore")
    def test_store_infra_error_exits_two(
        self, mock_store_cls: MagicMock, mock_connector_cls: MagicMock
    ) -> None:
        mock_connector_cls.return_value.is_available.return_value = True
        store = MagicMock()
        store.retire_former_champion.side_effect = StoreInfraError("boom")
        mock_store_cls.from_env.return_value = store

        rc = cmd_retire(_retire_args())
        assert rc == 2
