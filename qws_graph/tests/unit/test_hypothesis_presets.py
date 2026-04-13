"""Unit tests for QWS-0905: hypotheses_by_status + hypothesis_search presets and --findings flag.

Tests use mock GraphQueryService / mock store — no live Neo4j required.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from qws_graph.research.graph.query_presets import PRESET_CATALOG, run_preset

# ---------------------------------------------------------------------------
# Preset catalog tests
# ---------------------------------------------------------------------------


class TestHypothesisByStatusPreset:
    def test_preset_exists_in_catalog(self) -> None:
        assert "hypotheses_by_status" in PRESET_CATALOG

    def test_preset_has_no_required_params(self) -> None:
        spec = PRESET_CATALOG["hypotheses_by_status"]
        required = [p for p in spec.params if p.required]
        assert required == []

    def test_preset_requires_graph(self) -> None:
        assert PRESET_CATALOG["hypotheses_by_status"].requires_graph is True

    def test_run_preset_delegates_to_service(self) -> None:
        service = MagicMock()
        service.get_hypotheses_by_status_v1.return_value = [
            {
                "hypothesis_id": "aabbccddeeff",
                "title": "Bear sweep exploits liquidity",
                "status": "open",
                "findings": "Parked after session 3.",
                "created_at": "2026-01-10T09:00:00",
            }
        ]
        result = run_preset("hypotheses_by_status", {}, service=service)
        service.get_hypotheses_by_status_v1.assert_called_once()
        assert len(result) == 1
        assert result[0]["status"] == "open"
        assert result[0]["findings"] == "Parked after session 3."

    def test_run_preset_returns_empty_list_when_no_hypotheses(self) -> None:
        service = MagicMock()
        service.get_hypotheses_by_status_v1.return_value = []
        result = run_preset("hypotheses_by_status", {}, service=service)
        assert result == []


class TestHypothesisSearchPreset:
    def test_preset_exists_in_catalog(self) -> None:
        assert "hypothesis_search" in PRESET_CATALOG

    def test_preset_has_required_title_fragment_param(self) -> None:
        spec = PRESET_CATALOG["hypothesis_search"]
        required = [p for p in spec.params if p.required]
        assert len(required) == 1
        assert required[0].name == "title_fragment"

    def test_preset_requires_graph(self) -> None:
        assert PRESET_CATALOG["hypothesis_search"].requires_graph is True

    def test_run_preset_passes_title_fragment_to_service(self) -> None:
        service = MagicMock()
        service.get_hypothesis_search_v1.return_value = [
            {
                "hypothesis_id": "aabbccddeeff",
                "title": "MES sweep strategy",
                "status": "open",
                "findings": None,
            }
        ]
        result = run_preset(
            "hypothesis_search", {"title_fragment": "sweep"}, service=service
        )
        service.get_hypothesis_search_v1.assert_called_once_with(title_fragment="sweep")
        assert len(result) == 1
        assert result[0]["title"] == "MES sweep strategy"

    def test_run_preset_missing_title_fragment_raises(self) -> None:
        service = MagicMock()
        with pytest.raises(ValueError, match="title_fragment"):
            run_preset("hypothesis_search", {}, service=service)

    def test_run_preset_returns_empty_when_no_match(self) -> None:
        service = MagicMock()
        service.get_hypothesis_search_v1.return_value = []
        result = run_preset(
            "hypothesis_search", {"title_fragment": "xyznotfound"}, service=service
        )
        assert result == []


# ---------------------------------------------------------------------------
# --findings flag tests (via _cmd_hypothesis logic)
# ---------------------------------------------------------------------------


class TestFindingsFlag:
    """Tests for --findings flag on `qw record --hypothesis <id>`.

    Exercises cli._cmd_hypothesis Mode 5 via the store mock.
    """

    def _make_args(
        self,
        hypothesis: str = "aabbccddeeff",
        findings: str | None = None,
        status: str | None = None,
        tested_as: str | None = None,
        branched_from: str | None = None,
        rationale: str | None = None,
        timeout_seconds: int = 3,
        similarity_threshold: float | None = None,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            hypothesis=hypothesis,
            findings=findings,
            status=status,
            tested_as=tested_as,
            branched_from=branched_from,
            rationale=rationale,
            timeout_seconds=timeout_seconds,
            similarity_threshold=similarity_threshold,
        )

    def test_findings_update_calls_store_method(self) -> None:
        from qws_graph.research.graph.cli import _cmd_hypothesis

        args = self._make_args(findings="Session 3 notes — needs more data.")
        mock_store = MagicMock()
        mock_store.update_hypothesis_findings.return_value = True
        mock_connector = MagicMock()
        mock_connector.is_available.return_value = True

        with (
            patch("qws_graph.research.graph.cli.NeoConnector", return_value=mock_connector),
            patch("qws_graph.research.graph.cli.GraphStore") as mock_gs_class,
        ):
            mock_gs_class.from_env.return_value.__enter__ = lambda s: mock_store
            mock_gs_class.from_env.return_value.__exit__ = MagicMock(return_value=False)
            mock_gs_class.from_env.return_value = mock_store

            exit_code = _cmd_hypothesis(args)

        mock_store.update_hypothesis_findings.assert_called_once_with(
            "aabbccddeeff", "Session 3 notes — needs more data."
        )
        assert exit_code == 0

    def test_findings_not_found_returns_exit_1(self) -> None:
        from qws_graph.research.graph.cli import _cmd_hypothesis

        args = self._make_args(findings="some notes")
        mock_store = MagicMock()
        mock_store.update_hypothesis_findings.return_value = False
        mock_connector = MagicMock()
        mock_connector.is_available.return_value = True

        with (
            patch("qws_graph.research.graph.cli.NeoConnector", return_value=mock_connector),
            patch("qws_graph.research.graph.cli.GraphStore") as mock_gs_class,
        ):
            mock_gs_class.from_env.return_value = mock_store

            exit_code = _cmd_hypothesis(args)

        assert exit_code == 1

    def test_findings_neo4j_unavailable_returns_exit_2(self) -> None:
        from qws_graph.research.graph.cli import _cmd_hypothesis

        args = self._make_args(findings="some notes")
        mock_connector = MagicMock()
        mock_connector.is_available.return_value = False

        with patch("qws_graph.research.graph.cli.NeoConnector", return_value=mock_connector):
            exit_code = _cmd_hypothesis(args)

        assert exit_code == 2
