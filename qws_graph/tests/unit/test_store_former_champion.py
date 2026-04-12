"""Unit tests for GraphStore.degrade_champion and retire_former_champion (QWS-0801)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.store import GraphStore, StoreError, StoreInfraError


def _make_store() -> GraphStore:
    """Return a GraphStore with a mocked Neo4j driver."""
    with patch("qws_graph.research.graph.store.GraphDatabase"):
        store = GraphStore.__new__(GraphStore)
        store._driver = MagicMock()
        return store


# ---------------------------------------------------------------------------
# degrade_champion
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_former_champion_id(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # Champion exists
        session_mock.execute_read.return_value = True
        session_mock.execute_write.return_value = None

        result = store.degrade_champion("champ_001", "MaxDD breach -15%")

        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 12  # hash12 output

    def test_missing_reason_raises_value_error(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="non-empty"):
            store.degrade_champion("champ_001", "  ")

    def test_empty_reason_raises_value_error(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="non-empty"):
            store.degrade_champion("champ_001", "")

    def test_non_existent_champion_returns_none(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # Champion not found
        session_mock.execute_read.return_value = False

        result = store.degrade_champion("ghost_id", "some reason")
        assert result is None

    def test_neo4j_error_raises_store_infra_error(self) -> None:
        from neo4j.exceptions import Neo4jError

        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.side_effect = Neo4jError()

        with pytest.raises(StoreInfraError):
            store.degrade_champion("champ_001", "MaxDD breach")

    def test_reason_is_stripped(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.return_value = True
        session_mock.execute_write.return_value = None

        # Whitespace-only after strip → should raise (we test stripped as ""
        # but here we test that a reason with surrounding spaces is accepted)
        result = store.degrade_champion("champ_001", "  OOS fail  ")
        assert result is not None


# ---------------------------------------------------------------------------
# retire_former_champion
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_valid_retire_returns_true(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.return_value = True
        session_mock.execute_write.return_value = None

        result = store.retire_former_champion("fc_001", "No pivot hypothesis")
        assert result is True

    def test_valid_retire_without_note_returns_true(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.return_value = True
        session_mock.execute_write.return_value = None

        result = store.retire_former_champion("fc_001")
        assert result is True

    def test_non_existent_former_champion_returns_false(self) -> None:
        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.return_value = False

        result = store.retire_former_champion("ghost_fc_id")
        assert result is False

    def test_neo4j_error_raises_store_infra_error(self) -> None:
        from neo4j.exceptions import Neo4jError

        store = _make_store()
        session_mock = MagicMock()
        store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        store._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session_mock.execute_read.side_effect = Neo4jError()

        with pytest.raises(StoreInfraError):
            store.retire_former_champion("fc_001")
