"""Unit tests for GraphStore.degrade_champion and retire_former_champion (QWS-0801)."""

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
    with patch("qws_graph.research.graph.store.GraphDatabase") as mock_db:
        mock_driver = MagicMock()
        mock_db.driver.return_value = mock_driver
        store = GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")
        store._driver = mock_driver
        return store


def _session_returning(records: list[Any]) -> MagicMock:
    """Return a mock session context manager that yields records from execute_write."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write.return_value = records
    return mock_session


# ---------------------------------------------------------------------------
# degrade_champion
# ---------------------------------------------------------------------------

class TestDegradeChampion:
    def test_valid_degrade_returns_former_champion_id(self) -> None:
        store = _make_store()
        mock_record = {"former_champion_id": "abc123def456"}
        mock_session = _session_returning([mock_record])
        store._driver.session.return_value = mock_session

        result = store.degrade_champion(
            champion_id="demo_champ_001",
            oos_reason="MaxDD breached -15% in Oct CPI spike",
        )

        assert isinstance(result, str)
        assert len(result) == 12

    def test_empty_reason_raises_store_error(self) -> None:
        store = _make_store()
        with pytest.raises(StoreError, match="oos_reason must be a non-empty string"):
            store.degrade_champion(champion_id="demo_champ_001", oos_reason="")

    def test_whitespace_reason_raises_store_error(self) -> None:
        store = _make_store()
        with pytest.raises(StoreError, match="oos_reason must be a non-empty string"):
            store.degrade_champion(champion_id="demo_champ_001", oos_reason="   ")

    def test_champion_not_found_raises_store_error(self) -> None:
        store = _make_store()
        mock_session = _session_returning([])  # empty = not found
        store._driver.session.return_value = mock_session

        with pytest.raises(StoreError, match="not found in graph"):
            store.degrade_champion(
                champion_id="nonexistent_champion",
                oos_reason="OOS fail",
            )

    def test_sharpe_at_degradation_is_optional(self) -> None:
        store = _make_store()
        mock_record = {"former_champion_id": "abc123def456"}
        mock_session = _session_returning([mock_record])
        store._driver.session.return_value = mock_session

        # Should not raise when metrics_sharpe_at_degradation is None
        result = store.degrade_champion(
            champion_id="demo_champ_001",
            oos_reason="OOS fail",
            metrics_sharpe_at_degradation=None,
        )
        assert isinstance(result, str)

    def test_sharpe_at_degradation_passed_when_provided(self) -> None:
        store = _make_store()
        mock_record = {"former_champion_id": "abc123def456"}
        mock_session = _session_returning([mock_record])
        store._driver.session.return_value = mock_session

        result = store.degrade_champion(
            champion_id="demo_champ_001",
            oos_reason="Sharpe decay",
            metrics_sharpe_at_degradation=2.8,
        )
        assert isinstance(result, str)

    def test_infra_error_wraps_neo4j_error(self) -> None:
        from neo4j.exceptions import ServiceUnavailable
        store = _make_store()
        store._driver.session.side_effect = ServiceUnavailable("connection refused")

        with pytest.raises(StoreInfraError):
            store.degrade_champion(champion_id="demo_champ_001", oos_reason="OOS fail")


# ---------------------------------------------------------------------------
# retire_former_champion
# ---------------------------------------------------------------------------

class TestRetireFormerChampion:
    def test_valid_retire_with_note_returns_retired_id(self) -> None:
        store = _make_store()
        mock_record = {"retired_champion_id": "retired000abc"}
        mock_session = _session_returning([mock_record])
        store._driver.session.return_value = mock_session

        result = store.retire_former_champion(
            former_champion_id="abc123def456",
            retirement_note="No pivot hypothesis; logic dead-ended",
        )
        assert isinstance(result, str)
        assert len(result) == 12

    def test_retire_without_note_succeeds(self) -> None:
        store = _make_store()
        mock_record = {"retired_champion_id": "retired000abc"}
        mock_session = _session_returning([mock_record])
        store._driver.session.return_value = mock_session

        # note is optional — should not raise
        result = store.retire_former_champion(former_champion_id="abc123def456")
        assert isinstance(result, str)

    def test_former_champion_not_found_raises_store_error(self) -> None:
        store = _make_store()
        mock_session = _session_returning([])  # empty = not found
        store._driver.session.return_value = mock_session

        with pytest.raises(StoreError, match="not found in graph"):
            store.retire_former_champion(former_champion_id="nonexistent_fc")

    def test_infra_error_wraps_neo4j_error(self) -> None:
        from neo4j.exceptions import ServiceUnavailable
        store = _make_store()
        store._driver.session.side_effect = ServiceUnavailable("connection refused")

        with pytest.raises(StoreInfraError):
            store.retire_former_champion(former_champion_id="abc123def456")
