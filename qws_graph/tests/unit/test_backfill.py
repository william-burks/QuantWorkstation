# mypy: ignore-errors
"""Unit tests for family_id backfill store methods.

Tests cover GraphStore.audit_null_family_ids() and GraphStore.patch_family_id()
using FakeDriver duck-types — no live Neo4j required.
"""

from __future__ import annotations

from typing import Any

import pytest
from research.graph.store import GraphStore, StoreInfraError

# ---------------------------------------------------------------------------
# Fake driver helpers
# ---------------------------------------------------------------------------


class FakeRecord(dict):
    """dict-compatible record returned by tx.run() iterables."""


def _fake_record(**kwargs) -> FakeRecord:
    return FakeRecord(**kwargs)


class FakeTx:
    """Captures calls to tx.run() and returns a canned result list."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.queries: list[str] = []
        self.params: list[dict] = []

    def run(self, query: str, **kwargs) -> list[FakeRecord]:
        self.queries.append(query)
        self.params.append(kwargs)
        return [_fake_record(**r) for r in self._rows]


class FakeSession:
    """Context-manager session that routes read/write to the same FakeTx."""

    def __init__(self, rows: list[dict]) -> None:
        self.tx = FakeTx(rows)

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *_: Any) -> None:
        pass

    def execute_read(self, fn) -> Any:
        return fn(self.tx)

    def execute_write(self, fn) -> Any:
        return fn(self.tx)


class FakeDriver:
    """Minimal GraphDatabase.driver() substitute."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._sessions: list[FakeSession] = []

    def session(self, **_kw) -> FakeSession:
        s = FakeSession(self._rows)
        self._sessions.append(s)
        return s

    def verify_connectivity(self) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def last_tx(self) -> FakeTx:
        return self._sessions[-1].tx


class FakeErrorDriver:
    """Driver that always raises the given exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def session(self, **_kw):
        raise self._exc

    def close(self) -> None:
        pass


def _store_with_driver(driver) -> GraphStore:
    store = GraphStore.__new__(GraphStore)
    store._database = "neo4j"
    store._driver = driver
    return store


# ---------------------------------------------------------------------------
# audit_null_family_ids
# ---------------------------------------------------------------------------


class TestAuditNullFamilyIds:
    def test_returns_empty_list_when_no_nulls(self) -> None:
        store = _store_with_driver(FakeDriver(rows=[]))
        result = store.audit_null_family_ids()
        assert result == []

    def test_returns_one_row_per_null_strategy(self) -> None:
        rows = [
            {
                "strategy_id": "es-1h-bear",
                "logic_type": "TrendFollowing",
                "direction": "bear",
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "strategy_id": "nq-1h-bear",
                "logic_type": "TrendFollowing",
                "direction": "bear",
                "created_at": "2024-01-02T00:00:00",
            },
        ]
        store = _store_with_driver(FakeDriver(rows=rows))
        result = store.audit_null_family_ids()
        assert len(result) == 2
        assert result[0]["strategy_id"] == "es-1h-bear"
        assert result[1]["strategy_id"] == "nq-1h-bear"

    def test_result_dicts_include_expected_keys(self) -> None:
        rows = [
            {
                "strategy_id": "es-1h-bear",
                "logic_type": "Momentum",
                "direction": "bull",
                "created_at": "2024-03-01",
            },
        ]
        store = _store_with_driver(FakeDriver(rows=rows))
        result = store.audit_null_family_ids()
        assert set(result[0].keys()) == {"strategy_id", "logic_type", "direction", "created_at"}

    def test_uses_audit_query(self) -> None:
        from research.graph.cypher import AUDIT_NULL_FAMILY_ID_QUERY

        driver = FakeDriver(rows=[])
        store = _store_with_driver(driver)
        store.audit_null_family_ids()
        assert driver.last_tx.queries[0] == AUDIT_NULL_FAMILY_ID_QUERY

    def test_neo4j_error_raises_store_infra_error(self) -> None:
        from neo4j.exceptions import ServiceUnavailable

        store = _store_with_driver(FakeErrorDriver(ServiceUnavailable("boom")))
        with pytest.raises(StoreInfraError):
            store.audit_null_family_ids()

    def test_unexpected_error_raises_store_infra_error(self) -> None:
        store = _store_with_driver(FakeErrorDriver(RuntimeError("socket timeout")))
        with pytest.raises(StoreInfraError, match="Unexpected store error"):
            store.audit_null_family_ids()


# ---------------------------------------------------------------------------
# patch_family_id
# ---------------------------------------------------------------------------


class TestPatchFamilyId:
    def test_returns_true_when_strategy_found(self) -> None:
        rows = [{"strategy_id": "es-1h-bear"}]
        store = _store_with_driver(FakeDriver(rows=rows))
        result = store.patch_family_id("es-1h-bear", "abc123def456")
        assert result is True

    def test_returns_false_when_strategy_not_found(self) -> None:
        store = _store_with_driver(FakeDriver(rows=[]))
        result = store.patch_family_id("unknown-strategy", "abc123def456")
        assert result is False

    def test_passes_strategy_id_to_query(self) -> None:
        driver = FakeDriver(rows=[{"strategy_id": "es-1h-bear"}])
        store = _store_with_driver(driver)
        store.patch_family_id("es-1h-bear", "abc123def456")
        params = driver.last_tx.params[0]
        assert params["strategy_id"] == "es-1h-bear"

    def test_passes_family_id_to_query(self) -> None:
        driver = FakeDriver(rows=[{"strategy_id": "es-1h-bear"}])
        store = _store_with_driver(driver)
        store.patch_family_id("es-1h-bear", "abc123def456")
        params = driver.last_tx.params[0]
        assert params["family_id"] == "abc123def456"

    def test_uses_patch_query(self) -> None:
        from research.graph.cypher import PATCH_FAMILY_ID_QUERY

        driver = FakeDriver(rows=[{"strategy_id": "es-1h-bear"}])
        store = _store_with_driver(driver)
        store.patch_family_id("es-1h-bear", "abc123def456")
        assert driver.last_tx.queries[0] == PATCH_FAMILY_ID_QUERY

    def test_idempotent_second_call_still_returns_true(self) -> None:
        # Both calls hit the same fake driver; both return the row → True
        driver = FakeDriver(rows=[{"strategy_id": "es-1h-bear"}])
        store = _store_with_driver(driver)
        assert store.patch_family_id("es-1h-bear", "abc123def456") is True
        assert store.patch_family_id("es-1h-bear", "abc123def456") is True

    def test_neo4j_error_raises_store_infra_error(self) -> None:
        from neo4j.exceptions import ServiceUnavailable

        store = _store_with_driver(FakeErrorDriver(ServiceUnavailable("boom")))
        with pytest.raises(StoreInfraError):
            store.patch_family_id("es-1h-bear", "abc123def456")

    def test_unexpected_error_raises_store_infra_error(self) -> None:
        store = _store_with_driver(FakeErrorDriver(RuntimeError("connection reset")))
        with pytest.raises(StoreInfraError, match="Unexpected store error"):
            store.patch_family_id("es-1h-bear", "abc123def456")
