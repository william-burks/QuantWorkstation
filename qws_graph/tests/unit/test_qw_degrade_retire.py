"""Unit tests for QWS-0801 — `qw degrade` and `qw retire` CLI commands."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_degrade, cmd_retire
from research.graph.store import StoreInfraError


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------

class FakeGraphStore:
    def __init__(
        self,
        champion_exists: bool = True,
        fc_exists: bool = True,
        raise_infra: bool = False,
        champion_row: dict | None = None,
    ) -> None:
        self._champion_exists = champion_exists
        self._fc_exists = fc_exists
        self._raise_infra = raise_infra
        self._champion_row = champion_row or {
            "champion_id": "abc123",
            "strategy_id": "es-1h-bear",
            "metrics_sharpe": 3.1,
        }
        self.degraded: list[dict] = []
        self.retired: list[dict] = []

        # Simulate driver/session for champion lookup
        class _FakeTx:
            def __init__(inner, records):
                inner._records = records
            def run(inner, query, **kwargs):
                return iter(inner._records)

        class _FakeRecord:
            def __init__(inner, data):
                inner._data = data
            def __iter__(inner):
                return iter(inner._data.items())
            def get(inner, k, default=None):
                return inner._data.get(k, default)

        _rec = _FakeRecord(self._champion_row)

        class _FakeSession:
            def run(inner, query, **kwargs):
                if champion_exists:
                    return iter([_rec])
                return iter([])
            def __enter__(inner): return inner
            def __exit__(inner, *a): pass

        class _FakeDriver:
            def session(inner, **_kw): return _FakeSession()
            def close(inner): pass

        self._driver = _FakeDriver()
        self._database = "neo4j"

    def degrade_champion(self, **kwargs) -> bool:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._champion_exists:
            return False
        self.degraded.append(kwargs)
        return True

    def retire_former_champion(self, **kwargs) -> bool:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._fc_exists:
            return False
        self.retired.append(kwargs)
        return True

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_degrade(
    champion_id: str = "abc123",
    reason: str = "MaxDD breached -15%",
    available: bool = True,
    champion_exists: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    store = FakeGraphStore(champion_exists=champion_exists, raise_infra=raise_infra)
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {
            "from_env": staticmethod(lambda **_: store),
        }),
    )

    args = Namespace(champion=champion_id, reason=reason, timeout_seconds=3)
    code = cmd_degrade(args)
    return code, store


def _run_retire(
    former_champion_id: str = "fc001",
    note: str | None = None,
    available: bool = True,
    fc_exists: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    store = FakeGraphStore(fc_exists=fc_exists, raise_infra=raise_infra)
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {
            "from_env": staticmethod(lambda **_: store),
        }),
    )

    args = Namespace(former_champion=former_champion_id, note=note, timeout_seconds=3)
    code = cmd_retire(args)
    return code, store


# ---------------------------------------------------------------------------
# qw degrade tests
# ---------------------------------------------------------------------------

class TestCmdDegrade:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(monkeypatch=monkeypatch)
        assert code == 0

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        _run_degrade(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out

    def test_empty_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "reason" in err.lower()

    def test_whitespace_only_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="   ", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0

    def test_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(champion_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.degraded) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2

    def test_reason_passed_to_store(self, monkeypatch) -> None:
        code, store = _run_degrade(reason="CPI spike MaxDD breach", monkeypatch=monkeypatch)
        assert code == 0
        assert store.degraded[0]["oos_reason"] == "CPI spike MaxDD breach"

    def test_champion_id_passed_to_store(self, monkeypatch) -> None:
        code, store = _run_degrade(champion_id="xyz999", monkeypatch=monkeypatch)
        assert code == 0
        assert store.degraded[0]["champion_id"] == "xyz999"


# ---------------------------------------------------------------------------
# qw retire tests
# ---------------------------------------------------------------------------

class TestCmdRetire:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(monkeypatch=monkeypatch)
        assert code == 0

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        _run_retire(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out

    def test_fc_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(fc_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(available=False, monkeypatch=monkeypatch)
        assert code == 2

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2

    def test_retire_without_note_succeeds(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(note=None, monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1

    def test_retire_with_note_passes_note(self, monkeypatch) -> None:
        code, store = _run_retire(note="No pivot hypothesis", monkeypatch=monkeypatch)
        assert code == 0
        assert store.retired[0]["retirement_note"] == "No pivot hypothesis"

    def test_retire_without_note_passes_none(self, monkeypatch) -> None:
        code, store = _run_retire(note=None, monkeypatch=monkeypatch)
        assert code == 0
        assert store.retired[0]["retirement_note"] is None


# ---------------------------------------------------------------------------
# Cemetery view query preset
# ---------------------------------------------------------------------------

class TestFormerChampionsPreset:
    def test_former_champions_in_catalog(self) -> None:
        from research.graph.query_presets import PRESET_CATALOG
        assert "former_champions" in PRESET_CATALOG

    def test_former_champions_requires_no_params(self) -> None:
        from research.graph.query_presets import PRESET_CATALOG
        spec = PRESET_CATALOG["former_champions"]
        assert len(spec.params) == 0

    def test_former_champions_requires_graph(self) -> None:
        from research.graph.query_presets import PRESET_CATALOG
        spec = PRESET_CATALOG["former_champions"]
        assert spec.requires_graph is True

    def test_former_champions_preset_dispatches(self) -> None:
        from research.graph.query_presets import run_preset

        calls = []

        class FakeService:
            def get_former_champions_v1(self):
                calls.append("called")
                return [{"strategy_id": "es-1h-bear", "status": "DEGRADED"}]

        result = run_preset("former_champions", {}, service=FakeService())
        assert len(result) == 1
        assert result[0]["status"] == "DEGRADED"
        assert calls == ["called"]
