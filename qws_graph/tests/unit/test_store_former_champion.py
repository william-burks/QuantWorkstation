"""Unit tests for GraphStore.degrade_champion and retire_former_champion (QWS-0801)."""

from __future__ import annotations

import sys
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import GraphStore, StoreError, StoreInfraError

# ---------------------------------------------------------------------------
# Fake Neo4j driver infrastructure
# ---------------------------------------------------------------------------


class FakeRecord:
    def __init__(self, data: dict) -> None:
        self._data = data

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def values(self) -> list[object]:
        return list(self._data.values())

    def items(self):
        return self._data.items()

    def data(self) -> dict:
        return self._data


class FakeResult:
    def __init__(self, records: list[dict]) -> None:
        self._records = [FakeRecord(r) for r in records]

    def single(self) -> FakeRecord | None:
        return self._records[0] if self._records else None

    def __iter__(self):
        return iter(self._records)

    def consume(self) -> None:
        pass


class FakeTx:
    def __init__(self, champion_rows: list[dict], fc_rows: list[dict], write_rows: list[dict]) -> None:
        self.champion_rows = champion_rows
        self.fc_rows = fc_rows
        self.write_rows = write_rows
        self.ran: list[str] = []

    def run(self, query: str, **kwargs: object) -> FakeResult:
        self.ran.append(query[:40])
        if "MATCH (ch:Champion" in query:
            return FakeResult(self.champion_rows)
        if "MATCH (fc:FormerChampion" in query and "RETURN fc.champion_id" in query:
            return FakeResult(self.fc_rows)
        return FakeResult(self.write_rows)


class FakeSession:
    def __init__(
        self,
        champion_rows: list[dict] | None = None,
        fc_rows: list[dict] | None = None,
        write_rows: list[dict] | None = None,
    ) -> None:
        self._champion_rows = champion_rows or []
        self._fc_rows = fc_rows or []
        self._write_rows = write_rows or []
        self.tx = FakeTx(self._champion_rows, self._fc_rows, self._write_rows)

    def execute_read(self, fn):
        return fn(self.tx)

    def execute_write(self, fn):
        return fn(self.tx)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeDriver:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def session(self, database: str = "neo4j") -> FakeSession:
        return self._session


def _make_store(
    champion_rows: list[dict] | None = None,
    fc_rows: list[dict] | None = None,
    write_rows: list[dict] | None = None,
) -> GraphStore:
    store = GraphStore.__new__(GraphStore)
    store._database = "neo4j"
    store._driver = FakeDriver(
        FakeSession(
            champion_rows=champion_rows or [],
            fc_rows=fc_rows or [],
            write_rows=write_rows or [],
        )
    )
    return store


# ---------------------------------------------------------------------------
# degrade_champion tests
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_id(self) -> None:
        store = _make_store(
            champion_rows=[{"sid": "es-1h-bear"}],
            write_rows=[{"former_champion_id": "abc123def456"}],
        )
        result = store.degrade_champion("champ001", "MaxDD -15% breach")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_empty_reason_raises_store_error(self) -> None:
        store = _make_store()
        try:
            store.degrade_champion("champ001", "")
            assert False, "should have raised"
        except StoreError as e:
            assert "oos_reason" in str(e).lower() or "non-empty" in str(e).lower()

    def test_whitespace_reason_raises_store_error(self) -> None:
        store = _make_store()
        try:
            store.degrade_champion("champ001", "   ")
            assert False, "should have raised"
        except StoreError:
            pass

    def test_champion_not_found_raises_store_error(self) -> None:
        store = _make_store(
            champion_rows=[],  # no champion found
            write_rows=[],
        )
        try:
            store.degrade_champion("nonexistent", "valid reason")
            assert False, "should have raised"
        except StoreError as e:
            assert "not found" in str(e).lower()

    def test_former_champion_id_deterministic(self) -> None:
        """Two calls with same input produce different IDs (timestamp differs) — just verify format."""
        store = _make_store(
            champion_rows=[{"sid": "es-1h-bear"}],
            write_rows=[{"former_champion_id": "abc123def456"}],
        )
        result = store.degrade_champion("champ001", "OOS fail")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# retire_former_champion tests
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_valid_retire_returns_champion_id(self) -> None:
        store = _make_store(
            fc_rows=[{"champion_id": "champ001"}],
            write_rows=[{"retired_champion_id": "champ001"}],
        )
        result = store.retire_former_champion("fc001", retirement_note="Logic dead-ended")
        assert result == "champ001"

    def test_retire_without_note_succeeds(self) -> None:
        store = _make_store(
            fc_rows=[{"champion_id": "champ001"}],
            write_rows=[{"retired_champion_id": "champ001"}],
        )
        result = store.retire_former_champion("fc001")
        assert result == "champ001"

    def test_fc_not_found_raises_store_error(self) -> None:
        store = _make_store(fc_rows=[], write_rows=[])
        try:
            store.retire_former_champion("nonexistent")
            assert False, "should have raised"
        except StoreError as e:
            assert "not found" in str(e).lower()


# ---------------------------------------------------------------------------
# get_former_champions tests
# ---------------------------------------------------------------------------


class TestGetFormerChampions:
    def test_returns_list(self) -> None:
        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"

        class ResultWithResult:
            def __getitem__(self, key: str) -> object:
                return {
                    "former_champion_id": "fc001",
                    "strategy_id": "es-1h-bear",
                    "instrument": "ES",
                    "degraded_at": "2026-03-10T09:00:00",
                    "oos_reason": "MaxDD breach",
                    "retirement_note": None,
                    "status": "DEGRADED",
                }

        class FakeReadTx:
            def run(self, query: str, **kwargs: object):
                return [ResultWithResult()]

        class FakeReadSession:
            def execute_read(self, fn):
                return fn(FakeReadTx())

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        class FakeReadDriver:
            def session(self, database: str = "neo4j"):
                return FakeReadSession()

        store._driver = FakeReadDriver()
        results = store.get_former_champions()
        assert len(results) == 1
        assert results[0]["former_champion_id"] == "fc001"
        assert results[0]["status"] == "DEGRADED"
