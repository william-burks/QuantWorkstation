"""Unit tests for FormerChampion store methods (QWS-0801).

Tests: degrade_champion(), retire_former_champion().
Uses in-memory Neo4j doubles — no live connection required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.store import GraphStore, StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store() -> GraphStore:
    """Return a GraphStore with a mocked Neo4j driver."""
    with patch("qws_graph.research.graph.store.GraphDatabase"):
        store = GraphStore(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="test",
        )
    return store


def _mock_session(store: GraphStore, write_records: list[Any], read_record: Any = None) -> MagicMock:
    """Patch store._driver.session so execute_write returns write_records."""
    session_mock = MagicMock()
    session_mock.execute_write.return_value = write_records
    session_mock.execute_read.return_value = read_record
    session_mock.__enter__ = lambda s: s
    session_mock.__exit__ = MagicMock(return_value=False)
    store._driver.session = MagicMock(return_value=session_mock)  # type: ignore[method-assign]
    return session_mock


# ---------------------------------------------------------------------------
# degrade_champion
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_former_champion_id(self) -> None:
        store = _make_store()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: "demo-strategy-alpha" if k == "strategy_id" else "fc_abc123"
        )
        _mock_session(store, [row])

        result = store.degrade_champion("demo_champ_001", "OOS fail — MaxDD breach")
        assert isinstance(result, str)
        assert len(result) == 12  # hash12 output

    def test_empty_reason_raises_store_error(self) -> None:
        store = _make_store()
        with pytest.raises(StoreError, match="oos_reason must not be empty"):
            store.degrade_champion("demo_champ_001", "")

    def test_whitespace_reason_raises_store_error(self) -> None:
        store = _make_store()
        with pytest.raises(StoreError, match="oos_reason must not be empty"):
            store.degrade_champion("demo_champ_001", "   ")

    def test_nonexistent_champion_raises_store_error(self) -> None:
        store = _make_store()
        # empty records = champion not found
        _mock_session(store, [])
        with pytest.raises(StoreError, match="not found"):
            store.degrade_champion("nonexistent_id", "some valid reason")

    def test_neo4j_error_raises_infra_error(self) -> None:
        from neo4j.exceptions import Neo4jError

        store = _make_store()
        session_mock = MagicMock()
        session_mock.execute_write.side_effect = Neo4jError("connection refused")
        session_mock.__enter__ = lambda s: s
        session_mock.__exit__ = MagicMock(return_value=False)
        store._driver.session = MagicMock(return_value=session_mock)  # type: ignore[method-assign]

        with pytest.raises(StoreInfraError):
            store.degrade_champion("demo_champ_001", "valid reason")

    def test_optional_sharpe_passed_through(self) -> None:
        store = _make_store()
        row = MagicMock()
        session_mock = _mock_session(store, [row])

        store.degrade_champion("demo_champ_001", "OOS fail", metrics_sharpe=1.8)

        # Verify execute_write was called (sharpe value goes through Cypher param)
        session_mock.execute_write.assert_called_once()


# ---------------------------------------------------------------------------
# retire_former_champion
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def _make_store_with_retire_mocks(
        self,
        read_record: Any,
        write_records: list[Any],
    ) -> GraphStore:
        store = _make_store()
        session_mock = MagicMock()
        session_mock.execute_read.return_value = read_record
        session_mock.execute_write.return_value = write_records
        session_mock.__enter__ = lambda s: s
        session_mock.__exit__ = MagicMock(return_value=False)
        store._driver.session = MagicMock(return_value=session_mock)  # type: ignore[method-assign]
        return store

    def test_valid_retire_returns_retired_champion_id(self) -> None:
        read_row = MagicMock()
        read_row.__getitem__ = MagicMock(return_value="fc_abc123")
        write_row = MagicMock()
        store = self._make_store_with_retire_mocks(read_row, [write_row])

        result = store.retire_former_champion("fc_abc123", "No pivot; logic dead-ended")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_retire_without_note_succeeds(self) -> None:
        read_row = MagicMock()
        write_row = MagicMock()
        store = self._make_store_with_retire_mocks(read_row, [write_row])

        result = store.retire_former_champion("fc_abc123")
        assert isinstance(result, str)

    def test_nonexistent_former_champion_raises_store_error(self) -> None:
        store = self._make_store_with_retire_mocks(None, [])

        with pytest.raises(StoreError, match="not found"):
            store.retire_former_champion("nonexistent_fc_id")

    def test_neo4j_error_raises_infra_error(self) -> None:
        from neo4j.exceptions import Neo4jError

        store = _make_store()
        session_mock = MagicMock()
        session_mock.execute_read.side_effect = Neo4jError("timeout")
        session_mock.__enter__ = lambda s: s
        session_mock.__exit__ = MagicMock(return_value=False)
        store._driver.session = MagicMock(return_value=session_mock)  # type: ignore[method-assign]

        with pytest.raises(StoreInfraError):
            store.retire_former_champion("fc_abc123")
