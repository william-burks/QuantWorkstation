"""Unit tests for `qw degrade` and `qw retire` CLI commands."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_degrade, cmd_retire  # noqa: E402
from research.graph.store import StoreInfraError  # noqa: E402

# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeGraphStore:
    def __init__(
        self,
        degrade_result: str = "fc_abc123",
        retire_result: str = "rc_abc123",
        degrade_raises: Exception | None = None,
        retire_raises: Exception | None = None,
    ) -> None:
        self._degrade_result = degrade_result
        self._retire_result = retire_result
        self._degrade_raises = degrade_raises
        self._retire_raises = retire_raises
        self.degraded: list[tuple] = []
        self.retired: list[tuple] = []

    def degrade_champion(
        self,
        champion_id: str,
        oos_reason: str,
        metrics_sharpe_at_degradation: float | None = None,
    ) -> str:
        if self._degrade_raises:
            raise self._degrade_raises
        self.degraded.append((champion_id, oos_reason, metrics_sharpe_at_degradation))
        return self._degrade_result

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        if self._retire_raises:
            raise self._retire_raises
        self.retired.append((former_champion_id, retirement_note))
        return self._retire_result

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _patch_cli(monkeypatch, store: FakeGraphStore, available: bool = True) -> None:
    import research.graph.cli as cli_module
    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: FakeNeoConnector(available=available))
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
    )


# ---------------------------------------------------------------------------
# cmd_degrade tests
# ---------------------------------------------------------------------------


class TestCmdDegrade:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_abc", reason="OOS failed", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 0

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_abc", reason="OOS failed", sharpe=None, timeout_seconds=3)
        cmd_degrade(args)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "champ_abc" in out

    def test_empty_reason_returns_1(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_abc", reason="", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 1
        assert len(store.degraded) == 0
        err = capsys.readouterr().err
        assert "reason" in err.lower()

    def test_whitespace_reason_returns_1(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_abc", reason="   ", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 1
        assert len(store.degraded) == 0

    def test_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore(degrade_raises=ValueError("Champion not found: nonexistent"))
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="nonexistent", reason="valid reason", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 1
        err = capsys.readouterr().err
        assert "ERROR" in err

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore(degrade_raises=StoreInfraError("neo4j down"))
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_abc", reason="valid reason", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 2

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store, available=False)
        args = Namespace(champion="champ_abc", reason="valid reason", sharpe=None, timeout_seconds=3)
        code = cmd_degrade(args)
        assert code == 2
        assert len(store.degraded) == 0

    def test_champion_id_passed_verbatim(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(champion="champ_xyz999", reason="OOS fail", sharpe=None, timeout_seconds=3)
        cmd_degrade(args)
        assert store.degraded[0][0] == "champ_xyz999"

    def test_reason_passed_verbatim(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        reason = "MaxDD breached -15% in CPI spike; OOS fail"
        args = Namespace(champion="champ_abc", reason=reason, sharpe=None, timeout_seconds=3)
        cmd_degrade(args)
        assert store.degraded[0][1] == reason


# ---------------------------------------------------------------------------
# cmd_retire tests
# ---------------------------------------------------------------------------


class TestCmdRetire:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="fc_abc", note="Logic dead-ended", timeout_seconds=3)
        code = cmd_retire(args)
        assert code == 0

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="fc_abc", note=None, timeout_seconds=3)
        cmd_retire(args)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "fc_abc" in out

    def test_note_is_optional(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="fc_abc", note=None, timeout_seconds=3)
        code = cmd_retire(args)
        assert code == 0
        assert store.retired[0][1] is None

    def test_former_champion_not_found_returns_1(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore(retire_raises=ValueError("FormerChampion not found: nonexistent"))
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="nonexistent", note=None, timeout_seconds=3)
        code = cmd_retire(args)
        assert code == 1
        err = capsys.readouterr().err
        assert "ERROR" in err

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore(retire_raises=StoreInfraError("neo4j down"))
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="fc_abc", note=None, timeout_seconds=3)
        code = cmd_retire(args)
        assert code == 2

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store, available=False)
        args = Namespace(former_champion="fc_abc", note=None, timeout_seconds=3)
        code = cmd_retire(args)
        assert code == 2
        assert len(store.retired) == 0

    def test_note_passed_verbatim(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        note = "No pivot hypothesis; logic dead-ended"
        args = Namespace(former_champion="fc_abc", note=note, timeout_seconds=3)
        cmd_retire(args)
        assert store.retired[0][1] == note

    def test_former_champion_id_passed_verbatim(self, monkeypatch, capsys) -> None:
        store = FakeGraphStore()
        _patch_cli(monkeypatch, store)
        args = Namespace(former_champion="fc_xyz999", note=None, timeout_seconds=3)
        cmd_retire(args)
        assert store.retired[0][0] == "fc_xyz999"


# ---------------------------------------------------------------------------
# Argparse integration
# ---------------------------------------------------------------------------


class TestDegradeSubparser:
    def test_degrade_subcommand_registered(self) -> None:
        import research.graph.cli as cli_module
        assert callable(cli_module.cmd_degrade)

    def test_degrade_requires_champion(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "degrade", "--reason", "test"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0

    def test_degrade_requires_reason(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "degrade", "champ_abc"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0


class TestRetireSubparser:
    def test_retire_subcommand_registered(self) -> None:
        import research.graph.cli as cli_module
        assert callable(cli_module.cmd_retire)

    def test_retire_requires_former_champion(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "retire"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0
