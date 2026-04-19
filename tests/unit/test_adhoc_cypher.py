"""Unit tests for QWS-0906: qw query --cypher ad-hoc passthrough."""

from __future__ import annotations

import argparse
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from research.graph.store import GraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(records: list[dict[str, Any]] | None = None) -> GraphStore:
    """Return a GraphStore backed by a mock driver."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.execute_read.return_value = records or []

    store = GraphStore.__new__(GraphStore)
    store._database = "neo4j"
    store._driver = mock_driver
    return store


def _make_query_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "name": None,
        "cypher": None,
        "json": False,
        "param": None,
        "repo_root": None,
        "timeout_seconds": 3,
        "run_history": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# GraphStore.run_adhoc_cypher — write-keyword guard
# ---------------------------------------------------------------------------


class TestRunAdhocCypherWriteGuard:
    def test_blocks_set(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("SET r.sharpe = 1")

    def test_blocks_merge(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("MERGE (x:X)")

    def test_blocks_create(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("CREATE (n:Node {id: 1})")

    def test_blocks_delete(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("DELETE n")

    def test_blocks_remove(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("REMOVE n.prop")

    def test_blocks_drop(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("DROP INDEX idx_x")

    def test_blocks_call(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("CALL apoc.util.sleep(1000)")

    def test_blocks_load(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("LOAD CSV FROM 'file:///x.csv' AS row")

    def test_case_insensitive_block(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("set r.sharpe = 1")

    def test_blocks_leading_whitespace_write(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("   MERGE (x:X)")

    def test_comment_line_then_merge_is_blocked(self) -> None:
        store = _make_store()
        with pytest.raises(ValueError, match="write operation not permitted"):
            store.run_adhoc_cypher("// comment\nMERGE (x:X)")

    def test_match_allowed(self) -> None:
        store = _make_store(records=[{"run_id": "abc123"}])
        result = store.run_adhoc_cypher("MATCH (r:Run) RETURN r.run_id LIMIT 5")
        assert result == [{"run_id": "abc123"}]

    def test_returns_json_serializable_dicts(self) -> None:
        store = _make_store(records=[{"run_id": "abc", "sharpe": 2.5}])
        result = store.run_adhoc_cypher("MATCH (r:Run) RETURN r LIMIT 1")
        assert isinstance(result, list)
        assert isinstance(result[0], dict)
        # Verify JSON-serializable
        json.dumps(result)


# ---------------------------------------------------------------------------
# CLI: cmd_query --cypher path
# ---------------------------------------------------------------------------


class TestCmdQueryCypherPath:
    def test_write_keyword_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_query

        args = _make_query_args(cypher="SET r.sharpe = 1")
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = True
            mock_conn_cls.return_value = mock_conn
            with patch("research.graph.cli.GraphStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.run_adhoc_cypher.side_effect = ValueError(
                    "write operation not permitted: SET is a write keyword"
                )
                mock_store_cls.from_env.return_value = mock_store
                rc = cmd_query(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "write operation not permitted" in captured.err

    def test_merge_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_query

        args = _make_query_args(cypher="MERGE (x:X)")
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = True
            mock_conn_cls.return_value = mock_conn
            with patch("research.graph.cli.GraphStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.run_adhoc_cypher.side_effect = ValueError(
                    "write operation not permitted: MERGE is a write keyword"
                )
                mock_store_cls.from_env.return_value = mock_store
                rc = cmd_query(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "write operation not permitted" in captured.err

    def test_valid_match_returns_json_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_query

        args = _make_query_args(cypher="MATCH (r:Run) RETURN r.run_id LIMIT 5")
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = True
            mock_conn_cls.return_value = mock_conn
            with patch("research.graph.cli.GraphStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.run_adhoc_cypher.return_value = [
                    {"run_id": "abc123def456"},
                    {"run_id": "xyz789uvw012"},
                ]
                mock_store_cls.from_env.return_value = mock_store
                rc = cmd_query(args)
        assert rc == 0
        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.strip().splitlines() if ln]
        assert len(lines) == 2
        parsed = [json.loads(ln) for ln in lines]
        assert parsed[0]["run_id"] == "abc123def456"
        assert parsed[1]["run_id"] == "xyz789uvw012"

    def test_neo4j_unavailable_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        from research.graph.cli import cmd_query

        args = _make_query_args(cypher="MATCH (r:Run) RETURN r LIMIT 1")
        with patch("research.graph.cli.NeoConnector") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.is_available.return_value = False
            mock_conn_cls.return_value = mock_conn
            rc = cmd_query(args)
        assert rc == 2
        captured = capsys.readouterr()
        assert "unavailable" in captured.err
