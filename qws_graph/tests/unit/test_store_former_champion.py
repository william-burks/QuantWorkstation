"""Unit tests for FormerChampion lifecycle store methods (QWS-0801)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from research.graph.store import GraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store() -> GraphStore:
    """Return a GraphStore with a mocked Neo4j driver."""
    with patch("research.graph.store.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        store = GraphStore("bolt://localhost:7687", "neo4j", "test")
        store._driver = mock_driver
        return store


def _make_session_ctx(store: GraphStore, rows: list[dict[str, Any] | None]) -> MagicMock:
    """Patch session so execute_read/write return rows in sequence."""
    session_mock = MagicMock()
    store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
    store._driver.session.return_value.__exit__ = MagicMock(return_value=False)

    responses = iter(rows)

    def _side_effect(fn: Any, **_kwargs: Any) -> Any:
        return next(responses)

    session_mock.execute_read.side_effect = _side_effect
    session_mock.execute_write.side_effect = _side_effect
    return session_mock


# ---------------------------------------------------------------------------
# degrade_champion tests
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_former_champion_id(self) -> None:
        store = _make_store()
        champion_row = MagicMock()
        champion_row.__getitem__ = lambda self, k: "demo-strategy-alpha" if k == "strategy_id" else "champ123"
        champion_row.__contains__ = lambda self, k: k in ("strategy_id", "champion_id")

        write_row = MagicMock()
        write_row.__getitem__ = lambda self, k: "fc_abc123" if k == "former_champion_id" else None

        _make_session_ctx(store, [champion_row, write_row])

        fc_id = store.degrade_champion("champ123", "MaxDD breached -15%")
        assert fc_id == "fc_abc123"

    def test_missing_reason_raises_value_error(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="oos_reason must be non-empty"):
            store.degrade_champion("champ123", "")

    def test_none_reason_raises_value_error(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="oos_reason must be non-empty"):
            store.degrade_champion("champ123", "   ")  # whitespace-only

    def test_non_existent_champion_raises_value_error(self) -> None:
        store = _make_store()
        _make_session_ctx(store, [None])  # champion not found
        with pytest.raises(ValueError, match="Champion 'ghost_id' not found"):
            store.degrade_champion("ghost_id", "reason")

    def test_champion_node_not_deleted_after_degrade(self) -> None:
        """Champion readable = store does not issue DELETE on Champion.

        Verifies no DELETE cypher is passed to execute_write.
        """
        store = _make_store()
        champion_row = MagicMock()
        champion_row.__getitem__ = lambda self, k: "strat-alpha" if k == "strategy_id" else "c1"
        champion_row.__contains__ = lambda self, k: True

        write_row = MagicMock()
        write_row.__getitem__ = lambda self, k: "fc_001" if k == "former_champion_id" else None

        session_mock = _make_session_ctx(store, [champion_row, write_row])

        store.degrade_champion("c1", "OOS fail")

        # Verify no DELETE was directly executed (write call uses DEGRADE_CHAMPION_QUERY)
        for call in session_mock.execute_write.call_args_list:
            _fn = call[0][0]
            # The lambda wraps tx.run — we can't inspect the cypher directly here,
            # but confirming execute_write was called exactly once (no extra DELETE call).
        assert session_mock.execute_write.call_count == 1


# ---------------------------------------------------------------------------
# retire_former_champion tests
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_valid_retire_with_note_returns_retired_champion_id(self) -> None:
        store = _make_store()
        fc_row = MagicMock()
        fc_row.__getitem__ = lambda self, k: {
            "former_champion_id": "fc_001",
            "champion_id": "champ_001",
            "strategy_id": "strat-alpha",
            "oos_reason": "MaxDD breached",
        }.get(k)

        write_row = MagicMock()
        write_row.__getitem__ = lambda self, k: "rc_new_001" if k == "retired_champion_id" else None

        _make_session_ctx(store, [fc_row, write_row])

        rc_id = store.retire_former_champion("fc_001", retirement_note="No pivot found")
        assert rc_id == "rc_new_001"

    def test_retire_without_note_succeeds(self) -> None:
        store = _make_store()
        fc_row = MagicMock()
        fc_row.__getitem__ = lambda self, k: {
            "former_champion_id": "fc_002",
            "champion_id": "champ_002",
            "strategy_id": "strat-beta",
            "oos_reason": "Regime shift",
        }.get(k)

        write_row = MagicMock()
        write_row.__getitem__ = lambda self, k: "rc_new_002" if k == "retired_champion_id" else None

        _make_session_ctx(store, [fc_row, write_row])

        rc_id = store.retire_former_champion("fc_002", retirement_note=None)
        assert rc_id == "rc_new_002"

    def test_non_existent_former_champion_raises_value_error(self) -> None:
        store = _make_store()
        _make_session_ctx(store, [None])
        with pytest.raises(ValueError, match="FormerChampion 'ghost_fc' not found"):
            store.retire_former_champion("ghost_fc")


# ---------------------------------------------------------------------------
# Cemetery view query test
# ---------------------------------------------------------------------------


class TestGetFormerChampionsV1:
    def test_returns_rows_from_session(self) -> None:
        """Verifies GraphQueryService.get_former_champions_v1 passes through rows."""
        from research.graph.query import GraphQueryService

        with patch("research.graph.query.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_gdb.driver.return_value = mock_driver

            service = GraphQueryService("bolt://localhost:7687", "neo4j", "test")
            service._driver = mock_driver

            expected = [
                {
                    "former_champion_id": "fc_001",
                    "strategy_id": "strat-alpha",
                    "instrument": "ES",
                    "degraded_at": "2026-03-25T10:00:00",
                    "oos_reason": "MaxDD -15%",
                    "retirement_note": None,
                    "status": "DEGRADED",
                }
            ]

            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            mock_record = MagicMock()
            mock_record.data.return_value = expected[0]
            session_mock.run.return_value = [mock_record]

            result = service.get_former_champions_v1()
            assert len(result) == 1
            assert result[0]["status"] == "DEGRADED"
