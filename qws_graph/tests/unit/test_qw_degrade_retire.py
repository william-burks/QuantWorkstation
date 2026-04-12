"""Unit tests for QWS-0801 — qw degrade and qw retire CLI commands.

Covers:
- cmd_degrade: valid degrade, missing reason (argparse), empty reason, non-existent champion,
  Neo4j unavailable, infra error
- cmd_retire: valid retire with note, valid retire without note, non-existent former champion,
  Neo4j unavailable, infra error
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_degrade, cmd_retire
from research.graph.store import StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Fake Neo4j infrastructure
# ---------------------------------------------------------------------------


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


class FakeGraphStoreDegradeRetire:
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
        metrics_sharpe_at_degradation: float | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not oos_reason.strip():
            raise StoreError("oos_reason must be a non-empty string")
        if not self._champion_exists:
            raise StoreError(f"Champion {champion_id!r} not found in graph")
        fc_id = f"fc_{champion_id[:8]}"
        self.degraded.append({"champion_id": champion_id, "oos_reason": oos_reason, "fc_id": fc_id})
        return fc_id

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._former_champion_exists:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found in graph")
        rc_id = f"rc_{former_champion_id[:8]}"
        self.retired.append({"former_champion_id": former_champion_id, "note": retirement_note})
        return rc_id

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Helper runners
# ---------------------------------------------------------------------------


def _run_degrade(
    champion_id: str = "abc123def456",
    reason: str = "MaxDD breached -15%",
    sharpe: float | None = None,
    available: bool = True,
    champion_exists: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStoreDegradeRetire]:
    store = FakeGraphStoreDegradeRetire(
        champion_exists=champion_exists,
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

    args = Namespace(
        champion=champion_id,
        reason=reason,
        sharpe=sharpe,
        timeout_seconds=3,
    )
    code = cmd_degrade(args)
    return code, store


def _run_retire(
    former_champion_id: str = "fc_abc123de",
    note: str | None = "No pivot hypothesis",
    available: bool = True,
    former_champion_exists: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStoreDegradeRetire]:
    store = FakeGraphStoreDegradeRetire(
        former_champion_exists=former_champion_exists,
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

    args = Namespace(
        former_champion=former_champion_id,
        note=note,
        timeout_seconds=3,
    )
    code = cmd_retire(args)
    return code, store


# ---------------------------------------------------------------------------
# cmd_degrade tests
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_valid_degrade_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.degraded) == 1
        out = capsys.readouterr().out
        assert "OK" in out
        assert "FormerChampion" in out

    def test_empty_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0
        assert "ERROR" in capsys.readouterr().err

    def test_whitespace_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(reason="   ", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.degraded) == 0

    def test_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(
            champion_exists=False, monkeypatch=monkeypatch
        )
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "not found" in err.lower()

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_degrade(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.degraded) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, _ = _run_degrade(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2
        assert "ERROR" in capsys.readouterr().err

    def test_sharpe_optional(self, monkeypatch) -> None:
        code, store = _run_degrade(sharpe=1.8, monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.degraded) == 1

    def test_no_sharpe_still_works(self, monkeypatch) -> None:
        code, store = _run_degrade(sharpe=None, monkeypatch=monkeypatch)
        assert code == 0


# ---------------------------------------------------------------------------
# cmd_retire tests
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_valid_retire_with_note_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1
        assert store.retired[0]["note"] == "No pivot hypothesis"
        out = capsys.readouterr().out
        assert "OK" in out
        assert "RetiredChampion" in out

    def test_valid_retire_without_note_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(note=None, monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.retired) == 1
        assert store.retired[0]["note"] is None

    def test_former_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(
            former_champion_exists=False, monkeypatch=monkeypatch
        )
        assert code == 1
        assert len(store.retired) == 0
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "not found" in err.lower()

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_retire(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.retired) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, _ = _run_retire(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2
        assert "ERROR" in capsys.readouterr().err

    def test_retire_output_mentions_note(self, monkeypatch, capsys) -> None:
        _run_retire(note="Logic dead-ended", monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "Logic dead-ended" in out

    def test_retire_no_note_output_clean(self, monkeypatch, capsys) -> None:
        _run_retire(note=None, monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
