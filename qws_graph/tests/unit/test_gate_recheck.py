"""Unit tests for correlation gate re-check command (QWS-0804)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store() -> Any:
    """Return a GraphStore with a mocked Neo4j driver."""
    from research.graph.store import GraphStore

    with patch("research.graph.store.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        store = GraphStore("bolt://localhost:7687", "neo4j", "test")
        store._driver = mock_driver
        return store


def _mock_session(store: Any, rows: list[dict[str, Any]]) -> MagicMock:
    """Patch session so execute_read returns mocked rows."""
    session_mock = MagicMock()
    store._driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
    store._driver.session.return_value.__exit__ = MagicMock(return_value=False)

    def _side_effect(fn: Any, **_kwargs: Any) -> Any:
        # fn is the _read closure; call it with a tx that returns rows
        tx_mock = MagicMock()
        tx_mock.run.return_value = _build_neo4j_records(rows)
        return fn(tx_mock)

    session_mock.execute_read.side_effect = _side_effect
    return session_mock


def _build_neo4j_records(rows: list[dict[str, Any]]) -> list[MagicMock]:
    """Build fake Neo4j record objects from plain dicts."""
    records = []
    for row in rows:
        rec = MagicMock()
        rec.__getitem__ = lambda self, k, _row=row: _row[k]
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Store method tests
# ---------------------------------------------------------------------------


class TestGetCorrelationGateRecheckV1:
    def test_all_pass(self) -> None:
        store = _make_store()
        _mock_session(store, [
            {"candidate_id": "strat-alpha", "max_corr": 0.18},
            {"candidate_id": "strat-beta", "max_corr": 0.05},
        ])
        rows = store.get_correlation_gate_recheck_v1(corr_threshold=0.30)
        assert len(rows) == 2
        assert all(r["gate"] == "PASS" for r in rows)

    def test_partial_fail(self) -> None:
        store = _make_store()
        _mock_session(store, [
            {"candidate_id": "strat-alpha", "max_corr": 0.18},
            {"candidate_id": "strat-beta", "max_corr": 0.34},
        ])
        rows = store.get_correlation_gate_recheck_v1(corr_threshold=0.30)
        gates = {r["candidate_id"]: r["gate"] for r in rows}
        assert gates["strat-alpha"] == "PASS"
        assert gates["strat-beta"] == "FAIL"

    def test_empty_candidate_set(self) -> None:
        store = _make_store()
        _mock_session(store, [])
        rows = store.get_correlation_gate_recheck_v1()
        assert rows == []

    def test_empty_portfolio_no_corr_edges(self) -> None:
        """Candidate with no CORRELATED_WITH edges → max_corr=0.0, gate=PASS."""
        store = _make_store()
        _mock_session(store, [
            {"candidate_id": "strat-gamma", "max_corr": 0.0},
        ])
        rows = store.get_correlation_gate_recheck_v1(corr_threshold=0.30)
        assert rows[0]["gate"] == "PASS"
        assert rows[0]["max_corr"] == pytest.approx(0.0)

    def test_boundary_exactly_at_threshold_fails(self) -> None:
        """corr == threshold → FAIL (gate is strict <)."""
        store = _make_store()
        _mock_session(store, [
            {"candidate_id": "strat-delta", "max_corr": 0.30},
        ])
        rows = store.get_correlation_gate_recheck_v1(corr_threshold=0.30)
        assert rows[0]["gate"] == "FAIL"

    def test_threshold_customizable(self) -> None:
        store = _make_store()
        _mock_session(store, [
            {"candidate_id": "strat-alpha", "max_corr": 0.25},
        ])
        rows = store.get_correlation_gate_recheck_v1(corr_threshold=0.20)
        assert rows[0]["gate"] == "FAIL"


# ---------------------------------------------------------------------------
# CLI cmd_gate tests
# ---------------------------------------------------------------------------


class TestCmdGate:
    def _run_cmd(self, rows: list[dict[str, Any]], available: bool = True) -> tuple[int, str]:
        """Run cmd_gate and return (exit_code, stdout)."""
        import argparse
        import io
        import sys

        from research.graph.cli import cmd_gate

        args = argparse.Namespace(timeout_seconds=3)

        mock_store = MagicMock()
        mock_store.get_correlation_gate_recheck_v1.return_value = rows

        with (
            patch("research.graph.cli.NeoConnector") as mock_conn,
            patch("research.graph.store.GraphStore") as mock_gs_cls,
        ):
            mock_conn.return_value.is_available.return_value = available
            mock_gs_cls.from_env.return_value = mock_store

            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                code = cmd_gate(args)
            finally:
                sys.stdout = old_stdout

        return code, captured.getvalue()

    def test_all_pass_exit_0(self) -> None:
        rows = [
            {"candidate_id": "strat-alpha", "max_corr": 0.18, "gate": "PASS"},
            {"candidate_id": "strat-beta", "max_corr": 0.05, "gate": "PASS"},
        ]
        code, output = self._run_cmd(rows)
        assert code == 0
        assert "PASS" in output
        assert "2 / 2" in output

    def test_any_fail_exit_1(self) -> None:
        rows = [
            {"candidate_id": "strat-alpha", "max_corr": 0.18, "gate": "PASS"},
            {"candidate_id": "strat-beta", "max_corr": 0.34, "gate": "FAIL"},
        ]
        code, _ = self._run_cmd(rows)
        assert code == 1

    def test_empty_no_candidates_exit_0(self) -> None:
        code, output = self._run_cmd([])
        assert code == 0
        assert "No promotion candidates" in output

    def test_neo4j_unavailable_exit_1(self) -> None:
        code, _ = self._run_cmd([], available=False)
        assert code == 1

    def test_output_table_columns_present(self) -> None:
        rows = [
            {"candidate_id": "strat-abc123", "max_corr": 0.11, "gate": "PASS"},
        ]
        _, output = self._run_cmd(rows)
        assert "candidate_id" in output
        assert "max_corr" in output
        assert "gate" in output
        assert "strat-abc123" in output
