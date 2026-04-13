"""Unit tests for QWS-0906: qw patch --run surgical property correction."""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from research.graph.store import GraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(found: bool = True) -> GraphStore:
    """Return a GraphStore backed by a mock driver."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    # execute_read → run exists check
    mock_session.execute_read.return_value = found
    # execute_write → returns records list
    mock_session.execute_write.return_value = (
        [{"run_id": "test_run_001"}] if found else []
    )

    store = GraphStore.__new__(GraphStore)
    store._database = "neo4j"
    store._driver = mock_driver
    return store


def _make_patch_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "run_id": "test_run_001",
        "set": "sharpe=2.5",
        "dry_run": False,
        "timeout_seconds": 3,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# GraphStore.patch_run — key whitelist
# ---------------------------------------------------------------------------


class TestPatchRunWhitelist:
    def test_allowed_key_sharpe(self) -> None:
        store = _make_store(found=True)
        result = store.patch_run("test_run_001", "sharpe", "2.5")
        assert result is True

    def test_allowed_key_profit_factor(self) -> None:
        store = _make_store(found=True)
        result = store.patch_run("test_run_001", "profit_factor", "1.8")
        assert result is True

    def test_allowed_key_win_rate(self) -> None:
        store = _make_store(found=True)
        result = store.patch_run("test_run_001", "win_rate", "0.6")
        assert result is True

    def test_allowed_key_total_trades(self) -> None:
        store = _make_store(found=True)
        result = store.patch_run("test_run_001", "total_trades", "42")
        assert result is True

    def test_allowed_key_max_drawdown_r(self) -> None:
        store = _make_store(found=True)
        result = store.patch_run("test_run_001", "max_drawdown_r", "-1.5")
        assert result is True

    def test_blocked_key_run_id(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="key not patchable"):
            store.patch_run("test_run_001", "run_id", "bad")

    def test_blocked_key_strategy_id(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="key not patchable"):
            store.patch_run("test_run_001", "strategy_id", "bad")

    def test_blocked_key_created_at(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="key not patchable"):
            store.patch_run("test_run_001", "created_at", "2026-01-01")

    def test_unknown_key_blocked(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="key not patchable"):
            store.patch_run("test_run_001", "arbitrary_field", "x")

    def test_run_not_found_returns_false(self) -> None:
        store = _make_store(found=False)
        result = store.patch_run("nonexistent", "sharpe", "1.0")
        assert result is False

    def test_float_coercion(self) -> None:
        """Numeric strings are coerced to float before write."""
        store = _make_store(found=True)
        # If coercion fails the method would blow up — just verify it returns True
        result = store.patch_run("test_run_001", "sharpe", "3.14")
        assert result is True

    def test_empty_run_id_raises(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            store.patch_run("", "sharpe", "2.5")


# ---------------------------------------------------------------------------
# CLI: cmd_patch
# ---------------------------------------------------------------------------


class TestCmdPatch:
    def test_dry_run_prints_cypher_no_db(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args(dry_run=True)
        rc = cmd_patch(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out
        assert "MATCH" in captured.out
        assert "test_run_001" in captured.out

    def test_bad_key_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args(**{"set": "run_id=bad"})
        rc = cmd_patch(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "key not patchable" in captured.err

    def test_missing_equals_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args(**{"set": "sharpe2.5"})
        rc = cmd_patch(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "key=value" in captured.err

    def test_run_not_found_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args(run_id="nonexistent")
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = True
            mock_conn_cls.return_value = mock_conn
            with patch("research.graph.cli.GraphStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.patch_run.return_value = False
                mock_store_cls.from_env.return_value = mock_store
                rc = cmd_patch(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "run not found" in captured.err

    def test_successful_patch_exits_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args()
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = True
            mock_conn_cls.return_value = mock_conn
            with patch("research.graph.cli.GraphStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.patch_run.return_value = True
                mock_store_cls.from_env.return_value = mock_store
                rc = cmd_patch(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_neo4j_unavailable_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_patch

        args = _make_patch_args()
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = False
            mock_conn_cls.return_value = mock_conn
            rc = cmd_patch(args)
        assert rc == 2
        captured = capsys.readouterr()
        assert "unavailable" in captured.err
