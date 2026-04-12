"""Unit tests for `qw degrade` and `qw retire` CLI commands (QWS-0801)."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.cli import cmd_degrade, cmd_retire
from qws_graph.research.graph.store import StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _args(**kwargs):  # type: ignore[no-untyped-def]
    """Build a namespace object for argparse."""
    ns = MagicMock()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    if not hasattr(ns, "timeout_seconds"):
        ns.timeout_seconds = 3
    return ns


def _neo_available(available: bool):  # type: ignore[no-untyped-def]
    """Patch NeoConnector.is_available()."""
    return patch(
        "qws_graph.research.graph.cli.NeoConnector.is_available",
        return_value=available,
    )


def _store_degrade(return_value: str | None = "abc123def456", side_effect=None):  # type: ignore[no-untyped-def]
    kw = {}
    if side_effect is not None:
        kw["side_effect"] = side_effect
    else:
        kw["return_value"] = return_value
    return patch("qws_graph.research.graph.cli.GraphStore.degrade_champion", **kw)


def _store_retire(return_value: str | None = "def456ghi789", side_effect=None):  # type: ignore[no-untyped-def]
    kw = {}
    if side_effect is not None:
        kw["side_effect"] = side_effect
    else:
        kw["return_value"] = return_value
    return patch("qws_graph.research.graph.cli.GraphStore.retire_former_champion", **kw)


# ---------------------------------------------------------------------------
# cmd_degrade
# ---------------------------------------------------------------------------

class TestCmdDegrade:
    def test_valid_degrade_exits_0(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="demo_champ_001", reason="MaxDD breach")
        with _neo_available(True), _store_degrade():
            with patch("qws_graph.research.graph.cli.GraphStore.from_env"), \
                 patch("qws_graph.research.graph.cli.GraphStore.close"):
                code = cmd_degrade(args)
        assert code == 0

    def test_missing_reason_exits_1(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="demo_champ_001", reason="")
        code = cmd_degrade(args)
        assert code == 1
        captured = capsys.readouterr()
        assert "non-empty" in captured.err

    def test_whitespace_reason_exits_1(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="demo_champ_001", reason="   ")
        code = cmd_degrade(args)
        assert code == 1
        captured = capsys.readouterr()
        assert "non-empty" in captured.err

    def test_neo4j_unavailable_exits_2(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="demo_champ_001", reason="OOS fail")
        with _neo_available(False):
            code = cmd_degrade(args)
        assert code == 2

    def test_champion_not_found_exits_1(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="nonexistent_id", reason="OOS fail")
        err = StoreError("Champion 'nonexistent_id' not found in graph")
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.degrade_champion.side_effect = err
            mock_from_env.return_value = mock_store

            code = cmd_degrade(args)

        assert code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_infra_error_exits_2(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(champion="demo_champ_001", reason="OOS fail")
        err = StoreInfraError("Neo4j write failed")
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.degrade_champion.side_effect = err
            mock_from_env.return_value = mock_store

            code = cmd_degrade(args)

        assert code == 2


# ---------------------------------------------------------------------------
# cmd_retire
# ---------------------------------------------------------------------------

class TestCmdRetire:
    def test_valid_retire_with_note_exits_0(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(former_champion="abc123def456", note="Logic dead-ended")
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "def456ghi789"
            mock_from_env.return_value = mock_store

            code = cmd_retire(args)

        assert code == 0

    def test_retire_without_note_exits_0(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(former_champion="abc123def456", note=None)
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.retire_former_champion.return_value = "def456ghi789"
            mock_from_env.return_value = mock_store

            code = cmd_retire(args)

        assert code == 0

    def test_neo4j_unavailable_exits_2(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(former_champion="abc123def456", note=None)
        with _neo_available(False):
            code = cmd_retire(args)
        assert code == 2

    def test_former_champion_not_found_exits_1(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(former_champion="nonexistent_fc", note=None)
        err = StoreError("FormerChampion 'nonexistent_fc' not found in graph")
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.retire_former_champion.side_effect = err
            mock_from_env.return_value = mock_store

            code = cmd_retire(args)

        assert code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_infra_error_exits_2(self, capsys) -> None:  # type: ignore[no-untyped-def]
        args = _args(former_champion="abc123def456", note=None)
        err = StoreInfraError("Neo4j write failed")
        with _neo_available(True), \
             patch("qws_graph.research.graph.cli.GraphStore.from_env") as mock_from_env:
            mock_store = MagicMock()
            mock_store.retire_former_champion.side_effect = err
            mock_from_env.return_value = mock_store

            code = cmd_retire(args)

        assert code == 2


# ---------------------------------------------------------------------------
# Argument parsing tests (parser registration)
# ---------------------------------------------------------------------------

class TestArgParsing:
    def _parse(self, argv: list[str]):  # type: ignore[no-untyped-def]
        """Run main() argument parsing without executing the command."""
        import argparse
        from qws_graph.research.graph import cli as cli_mod

        # Rebuild parser by calling main with a no-op command hook
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        # Re-use main parser setup — import the configured parser directly
        import importlib, inspect
        # Parse using the real main() parser by monkey-patching sys.argv
        with patch("sys.argv", ["qw"] + argv):
            # Direct parser construction test
            pass

        return parser.parse_args(argv)

    def test_degrade_parser_requires_champion_and_reason(self) -> None:
        """qw degrade requires --champion and --reason."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "qws_graph.research.graph.cli", "degrade", "--help"],
            capture_output=True, text=True
        )
        assert "--champion" in result.stdout
        assert "--reason" in result.stdout

    def test_retire_parser_requires_former_champion(self) -> None:
        """qw retire requires --former-champion."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "qws_graph.research.graph.cli", "retire", "--help"],
            capture_output=True, text=True
        )
        assert "--former-champion" in result.stdout
