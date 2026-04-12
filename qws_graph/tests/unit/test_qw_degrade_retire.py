"""Unit tests for `qw degrade` and `qw retire` CLI commands (QWS-0801)."""

from __future__ import annotations

import subprocess
import sys
from argparse import Namespace
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_degrade, cmd_retire
from research.graph.store import StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Fake store / connector
# ---------------------------------------------------------------------------


class FakeGraphStore:
    def __init__(
        self,
        champion_exists: bool = True,
        fc_exists: bool = True,
        raise_store: bool = False,
        raise_infra: bool = False,
    ) -> None:
        self._champion_exists = champion_exists
        self._fc_exists = fc_exists
        self._raise_store = raise_store
        self._raise_infra = raise_infra
        self.degraded: list[tuple[str, str]] = []
        self.retired: list[tuple[str, str | None]] = []

    def degrade_champion(self, champion_id: str, oos_reason: str, **_: object) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if self._raise_store:
            raise StoreError(f"Champion {champion_id!r} not found in graph")
        if not self._champion_exists:
            raise StoreError(f"Champion {champion_id!r} not found in graph")
        self.degraded.append((champion_id, oos_reason))
        return "abc123def456"

    def retire_former_champion(self, former_champion_id: str, retirement_note: str | None = None) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if self._raise_store:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found in graph")
        if not self._fc_exists:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found in graph")
        self.retired.append((former_champion_id, retirement_note))
        return "champ001"

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_degrade(
    champion_id: str = "abc123def456",
    reason: str = "MaxDD breach -15%",
    available: bool = True,
    champion_exists: bool = True,
    raise_store: bool = False,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    store = FakeGraphStore(
        champion_exists=champion_exists,
        raise_store=raise_store,
        raise_infra=raise_infra,
    )
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
    )

    args = Namespace(champion_id=champion_id, reason=reason, timeout_seconds=3)
    code = cmd_degrade(args)
    return code, store


def _run_retire(
    former_champion_id: str = "fc001",
    note: str | None = "No pivot hypothesis",
    available: bool = True,
    fc_exists: bool = True,
    raise_store: bool = False,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    store = FakeGraphStore(
        fc_exists=fc_exists,
        raise_store=raise_store,
        raise_infra=raise_infra,
    )
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
    )

    args = Namespace(former_champion_id=former_champion_id, note=note, timeout_seconds=3)
    code = cmd_retire(args)
    return code, store


# ---------------------------------------------------------------------------
# cmd_degrade tests
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.degraded) == 1

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        _run_degrade(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "degraded" in out.lower() or "FormerChampion" in out

    def test_empty_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "reason" in err.lower() or "ERROR" in err

    def test_whitespace_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="   ", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0

    def test_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(champion_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "ERROR" in err

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.degraded) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2

    def test_reason_passed_verbatim(self, monkeypatch, capsys) -> None:
        reason = "OOS Sharpe 0.4 in live; MaxDD -17% Oct CPI spike"
        code, store = _run_degrade(reason=reason, monkeypatch=monkeypatch)
        assert code == 0
        assert store.degraded[0][1] == reason

    def test_champion_id_passed_verbatim(self, monkeypatch, capsys) -> None:
        cid = "deadbeef0011"
        code, store = _run_degrade(champion_id=cid, monkeypatch=monkeypatch)
        assert code == 0
        assert store.degraded[0][0] == cid


# ---------------------------------------------------------------------------
# cmd_retire tests
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        _run_retire(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "retired" in out.lower() or "RetiredChampion" in out

    def test_retire_without_note_succeeds(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(note=None, monkeypatch=monkeypatch)
        assert code == 0
        assert store.retired[0][1] is None

    def test_fc_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(fc_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "ERROR" in err

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.retired) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2

    def test_note_passed_verbatim(self, monkeypatch, capsys) -> None:
        note = "No viable pivot; logic fully exhausted"
        code, store = _run_retire(note=note, monkeypatch=monkeypatch)
        assert code == 0
        assert store.retired[0][1] == note


# ---------------------------------------------------------------------------
# Argparse integration
# ---------------------------------------------------------------------------


class TestDegradeSubparser:
    def test_degrade_subcommand_registered(self) -> None:
        import research.graph.cli as cli_module
        assert callable(cli_module.cmd_degrade)

    def test_degrade_requires_reason(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "degrade", "abc123"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0
        assert "reason" in result.stderr.lower() or "required" in result.stderr.lower()

    def test_degrade_requires_champion_id(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "degrade", "--reason", "test"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0


class TestRetireSubparser:
    def test_retire_subcommand_registered(self) -> None:
        import research.graph.cli as cli_module
        assert callable(cli_module.cmd_retire)

    def test_retire_requires_former_champion_id(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "retire"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0
