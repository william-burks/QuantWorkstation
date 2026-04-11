"""Unit tests for QWS-0601: Hypothesis & Research Journaling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.query_presets import (
    PRESET_CATALOG,
    run_preset,
    validate_params,
)
from research.graph.store import StoreError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store_mock(**kwargs: Any) -> MagicMock:
    store = MagicMock()
    for attr, val in kwargs.items():
        setattr(store, attr, val)
    return store


def _make_service_mock(**kwargs: Any) -> MagicMock:
    svc = MagicMock()
    for attr, val in kwargs.items():
        setattr(svc, attr, MagicMock(return_value=val))
    return svc


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

class TestHypothesisIdGeneration:
    def test_hash12_is_12_chars(self) -> None:
        from research.graph.ids import hash12
        result = hash12("test title", "2026-01-01T00:00:00")
        assert len(result) == 12
        assert result.isalnum()

    def test_same_inputs_same_id(self) -> None:
        from research.graph.ids import hash12
        r1 = hash12("same title", "2026-01-01T00:00:00")
        r2 = hash12("same title", "2026-01-01T00:00:00")
        assert r1 == r2

    def test_different_titles_different_ids(self) -> None:
        from research.graph.ids import hash12
        r1 = hash12("title A", "2026-01-01T00:00:00")
        r2 = hash12("title B", "2026-01-01T00:00:00")
        assert r1 != r2


# ---------------------------------------------------------------------------
# Store: create_hypothesis
# ---------------------------------------------------------------------------

class TestStoreCreateHypothesis:
    def test_create_hypothesis_calls_cypher(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_write.return_value = "abc123def456"

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        result = store.create_hypothesis("abc123def456", "Test title", source="user")
        assert result == "abc123def456"
        assert mock_session.execute_write.called

    def test_create_hypothesis_source_llm(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_write.return_value = "llm123abc456"

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        result = store.create_hypothesis("llm123abc456", "LLM title", source="llm")
        assert result == "llm123abc456"


# ---------------------------------------------------------------------------
# Store: update_hypothesis_status
# ---------------------------------------------------------------------------

class TestStoreUpdateHypothesisStatus:
    def _make_store(self, found: bool = True) -> Any:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_write.return_value = (
            [{"hypothesis_id": "abc123def456"}] if found else []
        )

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver
        return store

    def test_valid_status_confirmed(self) -> None:
        store = self._make_store(found=True)
        assert store.update_hypothesis_status("abc123def456", "confirmed") is True

    def test_valid_status_refuted(self) -> None:
        store = self._make_store(found=True)
        assert store.update_hypothesis_status("abc123def456", "refuted") is True

    def test_valid_status_abandoned(self) -> None:
        store = self._make_store(found=True)
        assert store.update_hypothesis_status("abc123def456", "abandoned") is True

    def test_valid_status_open(self) -> None:
        store = self._make_store(found=True)
        assert store.update_hypothesis_status("abc123def456", "open") is True

    def test_invalid_status_raises(self) -> None:
        store = self._make_store()
        with pytest.raises(ValueError, match="invalid hypothesis status"):
            store.update_hypothesis_status("abc123def456", "pending")

    def test_not_found_returns_false(self) -> None:
        store = self._make_store(found=False)
        assert store.update_hypothesis_status("notexist123", "confirmed") is False


# ---------------------------------------------------------------------------
# Store: link_hypothesis_tested_as
# ---------------------------------------------------------------------------

class TestStoreLinkHypothesisTestedAs:
    def test_strategy_not_found_raises(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        # strategy check returns False (not found)
        mock_session.execute_read.return_value = False

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        with pytest.raises(StoreError, match="not found"):
            store.link_hypothesis_tested_as("abc123def456", "nonexistent-strategy")

    def test_link_returns_true_when_found(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_read.return_value = True
        mock_session.execute_write.return_value = [{"hypothesis_id": "abc123", "strategy_id": "es-1h-bear-sweep"}]

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        result = store.link_hypothesis_tested_as("abc123def456", "es-1h-bear-sweep")
        assert result is True


# ---------------------------------------------------------------------------
# Store: link_hypothesis_branched_from
# ---------------------------------------------------------------------------

class TestStoreLinkHypothesisBranchedFrom:
    def test_node_not_found_raises(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_read.return_value = False

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        with pytest.raises(StoreError, match="not found"):
            store.link_hypothesis_branched_from("abc123def456", "bad-node-id", "some rationale")

    def test_link_returns_true_when_found(self) -> None:
        from research.graph.store import GraphStore

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_read.return_value = True
        mock_session.execute_write.return_value = [{"hypothesis_id": "abc123def456"}]

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = mock_driver

        result = store.link_hypothesis_branched_from("abc123def456", "es-1h-bear-sweep", "reason")
        assert result is True


# ---------------------------------------------------------------------------
# Query presets: catalog entries
# ---------------------------------------------------------------------------

class TestHypothesisPresetCatalog:
    def test_list_hypotheses_in_catalog(self) -> None:
        assert "list_hypotheses" in PRESET_CATALOG

    def test_hypothesis_audit_in_catalog(self) -> None:
        assert "hypothesis_audit" in PRESET_CATALOG

    def test_check_redundancy_in_catalog(self) -> None:
        assert "check_redundancy" in PRESET_CATALOG

    def test_list_hypotheses_requires_graph(self) -> None:
        assert PRESET_CATALOG["list_hypotheses"].requires_graph is True

    def test_list_hypotheses_no_params(self) -> None:
        assert len(PRESET_CATALOG["list_hypotheses"].params) == 0

    def test_hypothesis_audit_requires_hypothesis_id(self) -> None:
        spec = PRESET_CATALOG["hypothesis_audit"]
        required = {p.name for p in spec.params if p.required}
        assert "hypothesis_id" in required

    def test_check_redundancy_requires_hypothesis_id(self) -> None:
        spec = PRESET_CATALOG["check_redundancy"]
        required = {p.name for p in spec.params if p.required}
        assert "hypothesis_id" in required

    def test_validate_params_hypothesis_audit_missing_id(self) -> None:
        spec = PRESET_CATALOG["hypothesis_audit"]
        errors = validate_params(spec, {})
        assert any("hypothesis_id" in e for e in errors)

    def test_validate_params_check_redundancy_missing_id(self) -> None:
        spec = PRESET_CATALOG["check_redundancy"]
        errors = validate_params(spec, {})
        assert any("hypothesis_id" in e for e in errors)


# ---------------------------------------------------------------------------
# Query presets: run_preset routing
# ---------------------------------------------------------------------------

class FakeHypothesisService:
    """Duck-type for hypothesis query routing tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._hypotheses = [
            {"hypothesis_id": "abc123def456", "title": "Test", "status": "open", "created_at": "2026-01-01T00:00:00"},
        ]
        self._audit = [
            {"hypothesis_id": "abc123def456", "title": "Test", "status": "open", "strategy_id": None},
        ]
        self._redundancy = [
            {"hypothesis_id": "abc123def456", "title": "Test", "active_champion_matches": [], "aborted_strategy_matches": []},
        ]

    def get_list_hypotheses_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_list_hypotheses_v1", {}))
        return self._hypotheses

    def get_hypothesis_audit_v1(self, hypothesis_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_hypothesis_audit_v1", {"hypothesis_id": hypothesis_id}))
        return self._audit

    def get_check_redundancy_v1(self, hypothesis_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_check_redundancy_v1", {"hypothesis_id": hypothesis_id}))
        return self._redundancy

    def close(self) -> None:
        pass


class TestHypothesisPresetRouting:
    def test_list_hypotheses_routing(self) -> None:
        svc = FakeHypothesisService()
        results = run_preset("list_hypotheses", {}, service=svc)
        assert len(svc.calls) == 1
        assert svc.calls[0][0] == "get_list_hypotheses_v1"
        assert results == svc._hypotheses

    def test_hypothesis_audit_routing(self) -> None:
        svc = FakeHypothesisService()
        results = run_preset("hypothesis_audit", {"hypothesis_id": "abc123def456"}, service=svc)
        assert svc.calls[0] == ("get_hypothesis_audit_v1", {"hypothesis_id": "abc123def456"})
        assert results == svc._audit

    def test_check_redundancy_routing(self) -> None:
        svc = FakeHypothesisService()
        results = run_preset("check_redundancy", {"hypothesis_id": "abc123def456"}, service=svc)
        assert svc.calls[0] == ("get_check_redundancy_v1", {"hypothesis_id": "abc123def456"})
        assert results == svc._redundancy

    def test_list_hypotheses_requires_service(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("list_hypotheses", {}, service=None)


# ---------------------------------------------------------------------------
# CLI: qw record --hypothesis
# ---------------------------------------------------------------------------

class TestHypothesisCLI:
    def _make_args(self, **kwargs: Any) -> argparse.Namespace:
        defaults = {
            "hypothesis": None,
            "tested_as": None,
            "branched_from": None,
            "rationale": None,
            "status": None,
            "timeout_seconds": 3,
            "bundle": None,
            "oos": None,
            "file": None,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_create_hypothesis_success(self) -> None:
        from research.graph.cli import cmd_record

        mock_store = MagicMock()
        mock_store.create_hypothesis.return_value = "abc123def456"

        args = self._make_args(hypothesis="Tuesday London Open has a liquidity trap in CL bear")

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs:
            mock_nc.return_value.is_available.return_value = True
            mock_gs.from_env.return_value = mock_store

            result = cmd_record(args)

        assert result == 0
        assert mock_store.create_hypothesis.called

    def test_hypothesis_title_too_long(self) -> None:
        from research.graph.cli import cmd_record

        args = self._make_args(hypothesis="x" * 201)

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs, \
             patch("builtins.print"):
            mock_nc.return_value.is_available.return_value = True
            mock_store = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_store)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_gs.from_env.return_value = ctx

            result = cmd_record(args)

        assert result == 1

    def test_neo4j_unavailable_returns_2(self) -> None:
        from research.graph.cli import cmd_record

        args = self._make_args(hypothesis="test title")

        with patch("research.graph.cli.NeoConnector") as mock_nc:
            mock_nc.return_value.is_available.return_value = False
            result = cmd_record(args)

        assert result == 2

    def test_invalid_status_returns_1(self) -> None:
        from research.graph.cli import cmd_record

        args = self._make_args(hypothesis="abc123def456", status="pending")

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs:
            mock_nc.return_value.is_available.return_value = True
            mock_store = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_store)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_gs.from_env.return_value = ctx

            result = cmd_record(args)

        assert result == 1

    def test_tested_as_strategy_not_found(self) -> None:
        from research.graph.cli import _cmd_hypothesis

        args = self._make_args(hypothesis="abc123def456", tested_as="nonexistent-strategy")

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs:
            mock_nc.return_value.is_available.return_value = True
            mock_store = MagicMock()
            mock_store.link_hypothesis_tested_as.side_effect = StoreError("Strategy 'nonexistent-strategy' not found in graph")
            mock_gs.from_env.return_value = mock_store

            result = _cmd_hypothesis(args)

        assert result == 1

    def test_branched_from_requires_rationale(self) -> None:
        from research.graph.cli import _cmd_hypothesis

        args = self._make_args(hypothesis="abc123def456", branched_from="some-node-id", rationale=None)

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs:
            mock_nc.return_value.is_available.return_value = True
            mock_store = MagicMock()
            mock_gs.from_env.return_value = mock_store

            result = _cmd_hypothesis(args)

        assert result == 1

    def test_status_update_not_found_returns_1(self) -> None:
        from research.graph.cli import _cmd_hypothesis

        args = self._make_args(hypothesis="abc123def456", status="confirmed")

        with patch("research.graph.cli.NeoConnector") as mock_nc, \
             patch("research.graph.cli.GraphStore") as mock_gs:
            mock_nc.return_value.is_available.return_value = True
            mock_store = MagicMock()
            mock_store.update_hypothesis_status.return_value = False
            mock_gs.from_env.return_value = mock_store

            result = _cmd_hypothesis(args)

        assert result == 1


# ---------------------------------------------------------------------------
# MCP: log_hypothesis
# ---------------------------------------------------------------------------

class TestMcpLogHypothesis:
    def test_log_hypothesis_creates_with_llm_source(self) -> None:
        from research.graph.mcp_adapter import McpReadAdapter

        mock_service = MagicMock()
        adapter = McpReadAdapter(service=mock_service)

        mock_store = MagicMock()
        mock_store.create_hypothesis.return_value = "abc123def456"

        with patch.object(adapter, "_get_store", return_value=mock_store):
            result = adapter.log_hypothesis("Tuesday open liquidity trap in CL")

        assert result.ok is True
        assert result.data["source"] == "llm"
        mock_store.create_hypothesis.assert_called_once()
        call_kwargs = mock_store.create_hypothesis.call_args
        assert call_kwargs.kwargs.get("source") == "llm" or call_kwargs[1].get("source") == "llm" or call_kwargs[0][2] == "llm"

    def test_log_hypothesis_empty_title_returns_error(self) -> None:
        from research.graph.mcp_adapter import McpReadAdapter

        mock_service = MagicMock()
        adapter = McpReadAdapter(service=mock_service)
        result = adapter.log_hypothesis("")
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_log_hypothesis_title_too_long_returns_error(self) -> None:
        from research.graph.mcp_adapter import McpReadAdapter

        mock_service = MagicMock()
        adapter = McpReadAdapter(service=mock_service)
        result = adapter.log_hypothesis("x" * 201)
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_log_hypothesis_infra_error(self) -> None:
        from research.graph.mcp_adapter import McpReadAdapter

        mock_service = MagicMock()
        adapter = McpReadAdapter(service=mock_service)

        mock_store = MagicMock()
        mock_store.create_hypothesis.side_effect = RuntimeError("Neo4j down")

        with patch.object(adapter, "_get_store", return_value=mock_store):
            result = adapter.log_hypothesis("valid title")

        assert result.ok is False
        assert result.error.code == "INFRA_ERROR"
