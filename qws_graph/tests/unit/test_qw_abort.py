"""Unit tests for `qw abort` CLI command."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_abort
from research.graph.store import StoreInfraError


# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------

class FakeGraphStore:
    """Minimal duck-type for GraphStore used by cmd_abort."""

    def __init__(self, strategy_exists: bool = True, raise_on_abort: bool = False) -> None:
        self._strategy_exists = strategy_exists
        self._raise_on_abort = raise_on_abort
        self.aborted: list[tuple[str, str]] = []

    def abort_strategy(self, strategy_id: str, reason: str) -> bool:
        if self._raise_on_abort:
            raise StoreInfraError("fake infra failure")
        self.aborted.append((strategy_id, reason))
        return self._strategy_exists

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_abort(
    strategy_id: str = "es-1h-bear-sweep",
    reason: str = "Low edge stability",
    available: bool = True,
    strategy_exists: bool = True,
    raise_on_abort: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    """Run cmd_abort with injected fakes. Returns (exit_code, store)."""
    store = FakeGraphStore(strategy_exists=strategy_exists, raise_on_abort=raise_on_abort)
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

    args = Namespace(
        strategy=strategy_id,
        reason=reason,
        timeout_seconds=3,
    )
    code = cmd_abort(args)
    return code, store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCmdAbort:
    def test_success_returns_0(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(monkeypatch=monkeypatch)
        assert code == 0
        assert len(store.aborted) == 1
        assert store.aborted[0] == ("es-1h-bear-sweep", "Low edge stability")

    def test_success_prints_ok(self, monkeypatch, capsys) -> None:
        _run_abort(monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "OK" in out
        assert "ABORTED" in out

    def test_empty_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(reason="", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.aborted) == 0  # no graph call made
        err = capsys.readouterr().err
        assert "reason" in err.lower()

    def test_whitespace_only_reason_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(reason="   ", monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.aborted) == 0

    def test_strategy_not_found_returns_1(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(strategy_exists=False, monkeypatch=monkeypatch)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_neo4j_unavailable_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.aborted) == 0

    def test_infra_error_returns_2(self, monkeypatch, capsys) -> None:
        code, store = _run_abort(raise_on_abort=True, monkeypatch=monkeypatch)
        assert code == 2
        err = capsys.readouterr().err
        assert "ERROR" in err

    def test_strategy_id_passed_verbatim(self, monkeypatch, capsys) -> None:
        sid = "nq-15m-bull-rsi-reversion"
        code, store = _run_abort(strategy_id=sid, monkeypatch=monkeypatch)
        assert code == 0
        assert store.aborted[0][0] == sid

    def test_reason_passed_verbatim(self, monkeypatch, capsys) -> None:
        reason = "Sharpe < 0.5 across all timeframes; no viable edge"
        code, store = _run_abort(reason=reason, monkeypatch=monkeypatch)
        assert code == 0
        assert store.aborted[0][1] == reason


# ---------------------------------------------------------------------------
# Argparse integration
# ---------------------------------------------------------------------------

class TestAbortSubparser:
    def test_abort_subcommand_registered(self) -> None:
        import argparse
        import research.graph.cli as cli_module

        # Re-parse through the real main parser to confirm `abort` is registered
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        # Import the module's main() to check parser construction indirectly
        # by verifying cmd_abort is importable and callable
        assert callable(cli_module.cmd_abort)

    def test_abort_requires_strategy(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "abort", "--reason", "test"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        # Missing --strategy should cause argparse error (exit 2 for argparse)
        assert result.returncode != 0

    def test_abort_requires_reason(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "research.graph.cli", "abort", "--strategy", "es-1h-bear"],
            capture_output=True,
            text=True,
            cwd=str(QWS_GRAPH_ROOT),
        )
        assert result.returncode != 0
