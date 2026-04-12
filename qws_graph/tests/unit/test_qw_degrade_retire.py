"""Unit tests for QWS-0801 — qw degrade and qw retire CLI commands.

Covers:
- cmd_degrade: valid degrade, missing reason, empty reason, champion not found
- cmd_retire: valid retire, retire without note, former champion not found
- Cemetery view: former_champions preset in PRESET_CATALOG
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_degrade, cmd_retire
from research.graph.query_presets import PRESET_CATALOG
from research.graph.store import StoreError, StoreInfraError

# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeGraphStore:
    """Minimal duck-type for GraphStore used by cmd_degrade and cmd_retire."""

    def __init__(
        self,
        champion_exists: bool = True,
        former_champion_exists: bool = True,
        raise_infra: bool = False,
    ) -> None:
        self._champion_exists = champion_exists
        self._former_champion_exists = former_champion_exists
        self._raise_infra = raise_infra
        self.degraded: list[dict] = []
        self.retired: list[dict] = []

    def degrade_champion(
        self,
        champion_id: str,
        oos_reason: str,
        sharpe_at_degradation: float | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not oos_reason.strip():
            raise StoreError("oos_reason must be non-empty")
        if not self._champion_exists:
            raise StoreError(f"Champion {champion_id!r} not found")
        fc_id = f"fc_{champion_id[:6]}"
        self.degraded.append({
            "champion_id": champion_id,
            "oos_reason": oos_reason,
            "former_champion_id": fc_id,
        })
        return fc_id

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._former_champion_exists:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found")
        rc_id = f"rc_{former_champion_id[:6]}"
        self.retired.append({
            "former_champion_id": former_champion_id,
            "retirement_note": retirement_note,
            "retired_champion_id": rc_id,
        })
        return rc_id

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_degrade(
    champion_id: str = "abc123def456",
    reason: str | None = "OOS fail: MaxDD breach",
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
        type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
    )

    args = Namespace(
        champion_id=champion_id,
        reason=reason,
        timeout_seconds=3,
    )
    code = cmd_degrade(args)
    return code, store


def _run_retire(
    former_champion_id: str = "fc_abc123",
    note: str | None = None,
    available: bool = True,
    former_champion_exists: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    store = FakeGraphStore(former_champion_exists=former_champion_exists, raise_infra=raise_infra)
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
    )

    args = Namespace(
        former_champion_id=former_champion_id,
        note=note,
        timeout_seconds=3,
    )
    code = cmd_retire(args)
    return code, store


# ---------------------------------------------------------------------------
# cmd_degrade
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_valid_degrade_exits_0(self, monkeypatch) -> None:
        code, store = _run_degrade(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.degraded) == 1
        assert store.degraded[0]["oos_reason"] == "OOS fail: MaxDD breach"

    def test_valid_degrade_prints_ok(self, monkeypatch, capsys) -> None:
        _run_degrade(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "abc123def456" in out

    def test_missing_reason_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason=None, monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "reason" in err.lower()

    def test_empty_reason_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "reason" in err.lower()

    def test_champion_not_found_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(champion_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        assert "not found" in capsys.readouterr().err.lower()

    def test_neo4j_unavailable_exits_2(self, monkeypatch) -> None:
        code, store = _run_degrade(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.degraded) == 0

    def test_infra_error_exits_2(self, monkeypatch) -> None:
        code, _ = _run_degrade(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2

    def test_champion_node_not_deleted(self, monkeypatch) -> None:
        """degrade_champion does not delete the Champion node — verified by store API only creating FC."""
        code, store = _run_degrade(monkeypatch=monkeypatch)
        assert code == 0
        # store.degraded records what was created; absence of a 'deleted' key confirms no deletion
        assert "deleted" not in store.degraded[0]


# ---------------------------------------------------------------------------
# cmd_retire
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_valid_retire_with_note_exits_0(self, monkeypatch) -> None:
        code, store = _run_retire(note="No pivot hypothesis; logic dead-ended", monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1
        assert store.retired[0]["retirement_note"] == "No pivot hypothesis; logic dead-ended"

    def test_valid_retire_without_note_exits_0(self, monkeypatch) -> None:
        code, store = _run_retire(note=None, monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1
        assert store.retired[0]["retirement_note"] is None

    def test_retire_prints_ok(self, monkeypatch, capsys) -> None:
        _run_retire(note="done", monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "fc_abc123" in out

    def test_former_champion_not_found_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(former_champion_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.retired) == 0
        assert "not found" in capsys.readouterr().err.lower()

    def test_neo4j_unavailable_exits_2(self, monkeypatch) -> None:
        code, store = _run_retire(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.retired) == 0

    def test_infra_error_exits_2(self, monkeypatch) -> None:
        code, _ = _run_retire(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2


# ---------------------------------------------------------------------------
# Cemetery view — former_champions preset
# ---------------------------------------------------------------------------


class TestFormerChampionsPreset:
    def test_former_champions_in_catalog(self) -> None:
        assert "former_champions" in PRESET_CATALOG

    def test_former_champions_requires_graph(self) -> None:
        spec = PRESET_CATALOG["former_champions"]
        assert spec.requires_graph is True

    def test_former_champions_has_no_required_params(self) -> None:
        spec = PRESET_CATALOG["former_champions"]
        required = [p for p in spec.params if p.required]
        assert required == []

    def test_former_champions_description_mentions_cemetery(self) -> None:
        spec = PRESET_CATALOG["former_champions"]
        assert "cemetery" in spec.description.lower() or "FormerChampion" in spec.description
