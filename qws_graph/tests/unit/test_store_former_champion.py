"""Unit tests for QWS-0801 — FormerChampion lifecycle store methods.

Covers:
- GraphStore.degrade_champion() — valid demotion, champion not found
- GraphStore.retire_former_champion() — valid retirement, fc not found, note optional
"""

from __future__ import annotations

import sys
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import StoreInfraError


# ---------------------------------------------------------------------------
# Fake session / driver
# ---------------------------------------------------------------------------

class FakeRecord:
    def __init__(self, data: dict) -> None:
        self._data = data

    def data(self) -> dict:
        return self._data


class FakeTx:
    def __init__(self, records: list[FakeRecord]) -> None:
        self._records = records
        self.calls: list[tuple] = []

    def run(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return iter(self._records)


class FakeSession:
    def __init__(
        self,
        read_records: list[FakeRecord] | None = None,
        write_records: list[FakeRecord] | None = None,
    ) -> None:
        self._read_records = read_records or []
        self._write_records = write_records or []
        self.read_tx: FakeTx | None = None
        self.write_tx: FakeTx | None = None

    def execute_read(self, fn):
        tx = FakeTx(self._read_records)
        self.read_tx = tx
        return fn(tx)

    def execute_write(self, fn):
        tx = FakeTx(self._write_records)
        self.write_tx = tx
        return fn(tx)

    def run(self, query: str, **kwargs):
        return iter(self._read_records)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeDriver:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def session(self, **_kwargs):
        return self._session

    def close(self):
        pass


def _make_store(session: FakeSession):
    """Return a GraphStore with injected fake driver."""
    import research.graph.store as store_module

    store = object.__new__(store_module.GraphStore)
    store._driver = FakeDriver(session)  # noqa: SLF001
    store._database = "neo4j"
    return store


# ---------------------------------------------------------------------------
# degrade_champion tests
# ---------------------------------------------------------------------------

class TestDegradeChampion:
    def test_returns_true_when_champion_found(self) -> None:
        champ_row = FakeRecord({"champion_id": "abc123", "strategy_id": "es-1h-bear", "metrics_sharpe": 3.1})
        fc_row = FakeRecord({"former_champion_id": "fc001"})
        session = FakeSession(read_records=[champ_row], write_records=[fc_row])
        store = _make_store(session)
        result = store.degrade_champion(
            champion_id="abc123",
            oos_reason="MaxDD breached -15%",
            former_champion_id="fc001",
            strategy_id="es-1h-bear",
            degraded_at="2026-04-01T10:00:00",
        )
        assert result is True

    def test_returns_false_when_champion_not_found(self) -> None:
        session = FakeSession(read_records=[], write_records=[])
        store = _make_store(session)
        result = store.degrade_champion(
            champion_id="nonexistent",
            oos_reason="some reason",
            former_champion_id="fc002",
            strategy_id="es-1h-bear",
            degraded_at="2026-04-01T10:00:00",
        )
        assert result is False

    def test_passes_oos_reason_to_write(self) -> None:
        champ_row = FakeRecord({"champion_id": "abc123", "strategy_id": "es-1h-bear", "metrics_sharpe": 2.5})
        fc_row = FakeRecord({"former_champion_id": "fc003"})
        session = FakeSession(read_records=[champ_row], write_records=[fc_row])
        store = _make_store(session)
        store.degrade_champion(
            champion_id="abc123",
            oos_reason="Sharpe dropped below 1.5",
            former_champion_id="fc003",
            strategy_id="es-1h-bear",
            degraded_at="2026-04-01T10:00:00",
        )
        assert session.write_tx is not None
        call_kwargs = session.write_tx.calls[0][1]
        assert call_kwargs["oos_reason"] == "Sharpe dropped below 1.5"

    def test_passes_optional_sharpe(self) -> None:
        champ_row = FakeRecord({"champion_id": "abc123", "strategy_id": "es-1h-bear", "metrics_sharpe": 2.5})
        fc_row = FakeRecord({"former_champion_id": "fc004"})
        session = FakeSession(read_records=[champ_row], write_records=[fc_row])
        store = _make_store(session)
        store.degrade_champion(
            champion_id="abc123",
            oos_reason="reason",
            former_champion_id="fc004",
            strategy_id="es-1h-bear",
            degraded_at="2026-04-01T10:00:00",
            metrics_sharpe_at_degradation=2.5,
        )
        assert session.write_tx is not None
        call_kwargs = session.write_tx.calls[0][1]
        assert call_kwargs["metrics_sharpe_at_degradation"] == 2.5


# ---------------------------------------------------------------------------
# retire_former_champion tests
# ---------------------------------------------------------------------------

class TestRetireFormerChampion:
    def test_returns_true_when_fc_found(self) -> None:
        fc_row = FakeRecord({"former_champion_id": "fc001", "strategy_id": "es-1h-bear", "champion_id": "abc123"})
        rc_row = FakeRecord({"retired_champion_id": "rc001"})
        session = FakeSession(read_records=[fc_row], write_records=[rc_row])
        store = _make_store(session)
        result = store.retire_former_champion(
            former_champion_id="fc001",
            retired_champion_id="rc001",
            retired_at="2026-04-10T12:00:00",
            retirement_note="No pivot hypothesis; logic dead-ended",
        )
        assert result is True

    def test_returns_false_when_fc_not_found(self) -> None:
        session = FakeSession(read_records=[], write_records=[])
        store = _make_store(session)
        result = store.retire_former_champion(
            former_champion_id="nonexistent",
            retired_champion_id="rc002",
            retired_at="2026-04-10T12:00:00",
        )
        assert result is False

    def test_retire_without_note_uses_empty_string(self) -> None:
        fc_row = FakeRecord({"former_champion_id": "fc002", "strategy_id": "es-1h-bear", "champion_id": "abc123"})
        rc_row = FakeRecord({"retired_champion_id": "rc002"})
        session = FakeSession(read_records=[fc_row], write_records=[rc_row])
        store = _make_store(session)
        store.retire_former_champion(
            former_champion_id="fc002",
            retired_champion_id="rc002",
            retired_at="2026-04-10T12:00:00",
        )
        assert session.write_tx is not None
        call_kwargs = session.write_tx.calls[0][1]
        assert call_kwargs["retirement_note"] == ""

    def test_retire_passes_note(self) -> None:
        fc_row = FakeRecord({"former_champion_id": "fc003", "strategy_id": "es-1h-bear", "champion_id": "abc123"})
        rc_row = FakeRecord({"retired_champion_id": "rc003"})
        session = FakeSession(read_records=[fc_row], write_records=[rc_row])
        store = _make_store(session)
        store.retire_former_champion(
            former_champion_id="fc003",
            retired_champion_id="rc003",
            retired_at="2026-04-10T12:00:00",
            retirement_note="Confirmed edge decay; no recovery hypothesis",
        )
        assert session.write_tx is not None
        call_kwargs = session.write_tx.calls[0][1]
        assert call_kwargs["retirement_note"] == "Confirmed edge decay; no recovery hypothesis"
