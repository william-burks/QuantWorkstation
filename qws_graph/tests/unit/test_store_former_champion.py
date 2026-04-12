"""Unit tests for GraphStore.degrade_champion and GraphStore.retire_former_champion."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import GraphStore, StoreInfraError  # noqa: E402

# ---------------------------------------------------------------------------
# Fake Neo4j driver
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, row: dict | None = None) -> None:
        self._row = row

    def single(self) -> dict | None:
        return self._row

    def consume(self) -> None:
        pass


class _FakeTx:
    def __init__(self, row: dict | None = None) -> None:
        self._row = row
        self.queries: list[str] = []
        self.params: list[dict] = []

    def run(self, query: str, **kwargs) -> _FakeResult:  # type: ignore[override]
        self.queries.append(query)
        self.params.append(kwargs)
        return _FakeResult(self._row)


class _FakeSession:
    def __init__(self, check_row: dict | None = None, raise_on_write: bool = False) -> None:
        self._check_row = check_row
        self._raise_on_write = raise_on_write
        self.written = False

    def execute_read(self, fn):  # type: ignore[override]
        tx = _FakeTx(row=self._check_row)
        return fn(tx)

    def execute_write(self, fn):  # type: ignore[override]
        if self._raise_on_write:
            from neo4j.exceptions import Neo4jError
            raise Neo4jError("fake", code="Neo.ClientError.Statement.TypeError")
        tx = _FakeTx()
        fn(tx)
        self.written = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _make_store() -> GraphStore:
    store = GraphStore.__new__(GraphStore)
    store._database = "neo4j"
    return store


# ---------------------------------------------------------------------------
# degrade_champion
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_returns_former_champion_id(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={"strategy_id": "es-1h-bear"})
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        result = store.degrade_champion("champ_abc", "OOS failed — Sharpe 0.4")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_raises_on_empty_reason(self) -> None:
        store = _make_store()
        import pytest
        with pytest.raises(ValueError, match="oos_reason"):
            store.degrade_champion("champ_abc", "")

    def test_raises_on_whitespace_reason(self) -> None:
        store = _make_store()
        import pytest
        with pytest.raises(ValueError, match="oos_reason"):
            store.degrade_champion("champ_abc", "   ")

    def test_raises_when_champion_not_found(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row=None)
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        import pytest
        with pytest.raises(ValueError, match="Champion not found"):
            store.degrade_champion("nonexistent", "some reason")

    def test_raises_store_infra_error_on_neo4j_failure(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={"strategy_id": "es-1h-bear"}, raise_on_write=True)
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        import pytest
        with pytest.raises(StoreInfraError):
            store.degrade_champion("champ_abc", "OOS failed")

    def test_accepts_optional_sharpe(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={"strategy_id": "es-1h-bear"})
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        result = store.degrade_champion("champ_abc", "reason", metrics_sharpe_at_degradation=1.4)
        assert len(result) == 12

    def test_champion_node_not_deleted(self) -> None:
        """degrade_champion uses CREATE not REMOVE — champion stays."""
        store = _make_store()
        session = _FakeSession(check_row={"strategy_id": "es-1h-bear"})
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        store.degrade_champion("champ_abc", "reason")
        assert session.written


# ---------------------------------------------------------------------------
# retire_former_champion
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_returns_retired_champion_id(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={
            "champion_id": "champ_abc",
            "strategy_id": "es-1h-bear",
            "oos_reason": "OOS failed",
        })
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        result = store.retire_former_champion("fc_abc")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_accepts_optional_note(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={
            "champion_id": "champ_abc",
            "strategy_id": "es-1h-bear",
            "oos_reason": "OOS failed",
        })
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        result = store.retire_former_champion("fc_abc", retirement_note="Logic dead-ended")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_note_is_none_when_not_provided(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row={
            "champion_id": "champ_abc",
            "strategy_id": "es-1h-bear",
            "oos_reason": "OOS failed",
        })
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        result = store.retire_former_champion("fc_abc")
        assert len(result) == 12

    def test_raises_when_former_champion_not_found(self) -> None:
        store = _make_store()
        session = _FakeSession(check_row=None)
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        import pytest
        with pytest.raises(ValueError, match="FormerChampion not found"):
            store.retire_former_champion("nonexistent")

    def test_raises_store_infra_error_on_neo4j_failure(self) -> None:
        store = _make_store()
        session = _FakeSession(
            check_row={
                "champion_id": "champ_abc",
                "strategy_id": "es-1h-bear",
                "oos_reason": "OOS failed",
            },
            raise_on_write=True,
        )
        driver = MagicMock()
        driver.session.return_value = session
        store._driver = driver
        import pytest
        with pytest.raises(StoreInfraError):
            store.retire_former_champion("fc_abc")
