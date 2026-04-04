"""Unit tests for Story 4 lineage and pivot queries.

Covers:
- Strategy lineage ordered chain (AC1)
- Pivot query empty list when no explicit edges (AC2)
- Multi-hop traversal bounded at depth=1 (AC3)
- Cross-artifact correlation through shared Strategy anchors (AC4)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.query import (
    GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER,
    GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER,
    GET_STRATEGY_LINEAGE_V1_CYPHER,
    QUERY_VIEW_REGISTRY,
    get_cross_artifact_correlation_v1,
    get_downstream_champions_v1,
    get_strategy_lineage_v1,
)
from research.graph.query_models import CrossArtifactRowV1, StrategyLineageV1
from research.graph.query_presets import (
    PRESET_CATALOG,
    run_preset,
    validate_params,
    resolve_preset,
)


# ---------------------------------------------------------------------------
# Fake session helpers (same pattern as test_graph_query_models.py)
# ---------------------------------------------------------------------------

class FakeRecord:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def data(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self, responses: dict[str, list[dict[str, object]]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, query: str, **parameters: object):
        self.calls.append((query, parameters))
        return [FakeRecord(row) for row in self._responses.get(query, [])]


def _lineage_record(
    strategy_id: str,
    champion_id: str,
    freeze_date: str,
    oos_status: str = "pending",
    pivot_from_run_id: str | None = None,
    pivot_run_timestamp: str | None = None,
    pivot_run_artifact_path: str | None = None,
    pivot_config_id: str | None = None,
) -> dict[str, Any]:
    return {
        "result": {
            "strategy_id": strategy_id,
            "champion_id": champion_id,
            "freeze_date": freeze_date,
            "oos_status": oos_status,
            "pivot_from_run_id": pivot_from_run_id,
            "pivot_run_timestamp": pivot_run_timestamp,
            "pivot_run_artifact_path": pivot_run_artifact_path,
            "pivot_config_id": pivot_config_id,
        }
    }


def _champion_record(
    champion_id: str,
    strategy_id: str,
    freeze_date: str,
    oos_status: str = "pending",
    pivot_from_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "result": {
            "champion_id": champion_id,
            "strategy_id": strategy_id,
            "freeze_date": freeze_date,
            "oos_status": oos_status,
            "fragilities": [],
            "artifact_path": f"results/{champion_id}.md",
            "pivot_from_run_id": pivot_from_run_id,
            "metrics_summary": None,
        }
    }


def _correlation_record(
    anchor_strategy_id: str,
    related_strategy_id: str,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str,
    run_count: int = 0,
    champion_count: int = 0,
    latest_champion_id: str | None = None,
    latest_champion_freeze_date: str | None = None,
) -> dict[str, Any]:
    return {
        "result": {
            "anchor_strategy_id": anchor_strategy_id,
            "related_strategy_id": related_strategy_id,
            "instrument": instrument,
            "timeframe": timeframe,
            "direction": related_strategy_id.split("-")[2] if "-" in related_strategy_id else direction,
            "logic_type": logic_type,
            "run_count": run_count,
            "champion_count": champion_count,
            "latest_champion_id": latest_champion_id,
            "latest_champion_freeze_date": latest_champion_freeze_date,
        }
    }


class FakeGraphQueryService:
    """Minimal duck-type for GraphQueryService."""

    def __init__(
        self,
        downstream_champions: list[dict[str, Any]] | None = None,
        cross_artifact: list[dict[str, Any]] | None = None,
        strategy_lineage: list[dict[str, Any]] | None = None,
    ) -> None:
        self._downstream = downstream_champions or []
        self._cross_artifact = cross_artifact or []
        self._strategy_lineage = strategy_lineage or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_downstream_champions_v1(self, run_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_downstream_champions_v1", {"run_id": run_id}))
        return self._downstream

    def get_cross_artifact_correlation_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_cross_artifact_correlation_v1", {"strategy_id": strategy_id}))
        return self._cross_artifact

    def get_strategy_lineage_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_strategy_lineage_v1", {"strategy_id": strategy_id}))
        return self._strategy_lineage

    def get_recent_champions_v1(self, limit: int = 20) -> list[dict[str, Any]]:
        return []

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# AC1 — Strategy lineage query returns ordered chain
# ---------------------------------------------------------------------------

class TestStrategyLineageOrderedChain:
    def test_single_champion_returns_one_row(self) -> None:
        session = FakeSession({
            GET_STRATEGY_LINEAGE_V1_CYPHER: [
                _lineage_record("es-1h-bear-sweep", "champ-001", "2026-04-01", pivot_from_run_id="run-001"),
            ]
        })
        rows = get_strategy_lineage_v1(session, "es-1h-bear-sweep")
        assert len(rows) == 1
        assert rows[0]["champion_id"] == "champ-001"
        assert rows[0]["pivot_from_run_id"] == "run-001"

    def test_multiple_champions_ordered_by_freeze_date_desc(self) -> None:
        session = FakeSession({
            GET_STRATEGY_LINEAGE_V1_CYPHER: [
                _lineage_record("es-1h-bear-sweep", "champ-002", "2026-03-01"),
                _lineage_record("es-1h-bear-sweep", "champ-003", "2026-04-01"),
                _lineage_record("es-1h-bear-sweep", "champ-001", "2026-02-01"),
            ]
        })
        rows = get_strategy_lineage_v1(session, "es-1h-bear-sweep")
        freeze_dates = [r["freeze_date"] for r in rows]
        assert freeze_dates == sorted(freeze_dates, reverse=True)

    def test_champion_without_pivot_edge_included(self) -> None:
        session = FakeSession({
            GET_STRATEGY_LINEAGE_V1_CYPHER: [
                _lineage_record("es-1h-bear-sweep", "champ-001", "2026-04-01", pivot_from_run_id=None),
            ]
        })
        rows = get_strategy_lineage_v1(session, "es-1h-bear-sweep")
        assert len(rows) == 1
        assert rows[0]["pivot_from_run_id"] is None

    def test_empty_strategy_returns_empty_list(self) -> None:
        session = FakeSession({GET_STRATEGY_LINEAGE_V1_CYPHER: []})
        rows = get_strategy_lineage_v1(session, "es-1h-bear-sweep")
        assert rows == []

    def test_output_has_stable_keys(self) -> None:
        session = FakeSession({
            GET_STRATEGY_LINEAGE_V1_CYPHER: [
                _lineage_record("es-1h-bear-sweep", "champ-001", "2026-04-01"),
            ]
        })
        row = get_strategy_lineage_v1(session, "es-1h-bear-sweep")[0]
        expected_keys = {
            "version", "strategy_id", "champion_id", "freeze_date", "oos_status",
            "pivot_from_run_id", "pivot_run_timestamp", "pivot_run_artifact_path", "pivot_config_id",
        }
        assert set(row) == expected_keys

    def test_strategy_lineage_registered_in_query_view_registry(self) -> None:
        assert "get_strategy_lineage_v1" in QUERY_VIEW_REGISTRY

    def test_strategy_lineage_preset_exists(self) -> None:
        spec = resolve_preset("strategy_lineage")
        assert spec.name == "strategy_lineage"


# ---------------------------------------------------------------------------
# AC2 — Pivot query returns empty list when no explicit pivot edges exist
# ---------------------------------------------------------------------------

class TestDownstreamChampionsNoPivotEdge:
    def test_no_pivot_edges_returns_empty_list(self) -> None:
        session = FakeSession({GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER: []})
        rows = get_downstream_champions_v1(session, "run-001")
        assert rows == []

    def test_run_id_passed_as_parameter(self) -> None:
        session = FakeSession({GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER: []})
        get_downstream_champions_v1(session, "run-abc")
        assert session.calls[0][1] == {"run_id": "run-abc"}

    def test_champions_with_pivot_returned(self) -> None:
        session = FakeSession({
            GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER: [
                _champion_record("champ-001", "es-1h-bear-sweep", "2026-04-01", pivot_from_run_id="run-001"),
            ]
        })
        rows = get_downstream_champions_v1(session, "run-001")
        assert len(rows) == 1
        assert rows[0]["champion_id"] == "champ-001"
        assert rows[0]["pivot_from_run_id"] == "run-001"

    def test_multiple_downstream_champions_ordered(self) -> None:
        session = FakeSession({
            GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER: [
                _champion_record("champ-002", "nq-1h-bear-sweep", "2026-03-15", pivot_from_run_id="run-001"),
                _champion_record("champ-001", "es-1h-bear-sweep", "2026-04-01", pivot_from_run_id="run-001"),
            ]
        })
        rows = get_downstream_champions_v1(session, "run-001")
        # Both returned; freeze_date ordering is delegated to Cypher ORDER BY
        assert len(rows) == 2
        champion_ids = {r["champion_id"] for r in rows}
        assert champion_ids == {"champ-001", "champ-002"}

    def test_reuses_champion_details_v1_dto(self) -> None:
        session = FakeSession({
            GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER: [
                _champion_record("champ-001", "es-1h-bear-sweep", "2026-04-01"),
            ]
        })
        row = get_downstream_champions_v1(session, "run-001")[0]
        assert row["version"] == "v1"
        assert "fragilities" in row
        assert "metrics_summary" in row

    def test_registered_in_query_view_registry(self) -> None:
        assert "get_downstream_champions_v1" in QUERY_VIEW_REGISTRY

    def test_downstream_champions_preset_exists(self) -> None:
        spec = resolve_preset("downstream_champions")
        assert spec.name == "downstream_champions"
        assert spec.requires_graph is True

    def test_downstream_champions_preset_requires_run_id(self) -> None:
        spec = resolve_preset("downstream_champions")
        errors = validate_params(spec, {})
        assert any("run_id" in e for e in errors)

    def test_downstream_champions_preset_routes_to_view(self) -> None:
        service = FakeGraphQueryService(downstream_champions=[{"champion_id": "c1"}])
        results = run_preset("downstream_champions", {"run_id": "run-001"}, service=service)
        assert service.calls[0][0] == "get_downstream_champions_v1"
        assert results == [{"champion_id": "c1"}]

    def test_downstream_champions_preset_empty_when_no_edges(self) -> None:
        service = FakeGraphQueryService(downstream_champions=[])
        results = run_preset("downstream_champions", {"run_id": "run-no-pivots"}, service=service)
        assert results == []


# ---------------------------------------------------------------------------
# AC3 — Multi-hop lineage traversal bounded and documented
# ---------------------------------------------------------------------------

class TestTraversalDepthBounded:
    def test_get_strategy_lineage_cypher_is_single_hop(self) -> None:
        # The Cypher must not contain variable-length path patterns like [*..N].
        # Depth is fixed: Strategy→Champion→Run (one hop beyond the anchor).
        assert "[*" not in GET_STRATEGY_LINEAGE_V1_CYPHER
        assert "PIVOTED_FROM" in GET_STRATEGY_LINEAGE_V1_CYPHER

    def test_get_downstream_champions_cypher_is_single_hop(self) -> None:
        assert "[*" not in GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER
        assert "PIVOTED_FROM" in GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER

    def test_get_cross_artifact_cypher_is_single_hop(self) -> None:
        assert "[*" not in GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER

    def test_get_downstream_champions_docstring_documents_depth(self) -> None:
        doc = get_downstream_champions_v1.__doc__ or ""
        assert "depth" in doc.lower()

    def test_get_cross_artifact_docstring_documents_depth(self) -> None:
        doc = get_cross_artifact_correlation_v1.__doc__ or ""
        assert "depth" in doc.lower()

    def test_lineage_view_only_traverses_explicit_pivot_edges(self) -> None:
        # Verify docstring states explicit-pivot-only policy.
        doc = get_downstream_champions_v1.__doc__ or ""
        assert "explicit" in doc.lower() or "PIVOTED_FROM" in doc


# ---------------------------------------------------------------------------
# AC4 — Cross-artifact correlation through shared Strategy anchors
# ---------------------------------------------------------------------------

class TestCrossArtifactCorrelation:
    def test_no_related_strategies_returns_empty_list(self) -> None:
        session = FakeSession({GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER: []})
        rows = get_cross_artifact_correlation_v1(session, "es-1h-bear-sweep")
        assert rows == []

    def test_related_strategy_returned(self) -> None:
        session = FakeSession({
            GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER: [
                {
                    "result": {
                        "anchor_strategy_id": "es-1h-bear-sweep",
                        "related_strategy_id": "nq-1h-bear-sweep",
                        "instrument": "NQ",
                        "timeframe": "1H",
                        "direction": "bear",
                        "logic_type": "sweep",
                        "run_count": 3,
                        "champion_count": 1,
                        "latest_champion_id": "champ-nq-001",
                        "latest_champion_freeze_date": "2026-04-01",
                    }
                }
            ]
        })
        rows = get_cross_artifact_correlation_v1(session, "es-1h-bear-sweep")
        assert len(rows) == 1
        assert rows[0]["anchor_strategy_id"] == "es-1h-bear-sweep"
        assert rows[0]["related_strategy_id"] == "nq-1h-bear-sweep"
        assert rows[0]["instrument"] == "NQ"

    def test_anchor_strategy_not_in_results(self) -> None:
        # The Cypher WHERE clause excludes anchor from related set.
        assert "strategy_id <> anchor.strategy_id" in GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER

    def test_anchors_on_logic_type_and_direction(self) -> None:
        # The correlation axis must be logic_type AND direction.
        assert "logic_type = anchor.logic_type" in GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER
        assert "direction = anchor.direction" in GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER

    def test_output_has_stable_keys(self) -> None:
        session = FakeSession({
            GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER: [
                {
                    "result": {
                        "anchor_strategy_id": "es-1h-bear-sweep",
                        "related_strategy_id": "nq-1h-bear-sweep",
                        "instrument": "NQ",
                        "timeframe": "1H",
                        "direction": "bear",
                        "logic_type": "sweep",
                        "run_count": 0,
                        "champion_count": 0,
                        "latest_champion_id": None,
                        "latest_champion_freeze_date": None,
                    }
                }
            ]
        })
        row = get_cross_artifact_correlation_v1(session, "es-1h-bear-sweep")[0]
        expected_keys = {
            "version",
            "anchor_strategy_id",
            "related_strategy_id",
            "instrument",
            "timeframe",
            "direction",
            "logic_type",
            "run_count",
            "champion_count",
            "latest_champion_id",
            "latest_champion_freeze_date",
        }
        assert set(row) == expected_keys

    def test_output_is_json_serializable(self) -> None:
        session = FakeSession({
            GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER: [
                {
                    "result": {
                        "anchor_strategy_id": "es-1h-bear-sweep",
                        "related_strategy_id": "nq-1h-bear-sweep",
                        "instrument": "NQ",
                        "timeframe": "1H",
                        "direction": "bear",
                        "logic_type": "sweep",
                        "run_count": 2,
                        "champion_count": 1,
                        "latest_champion_id": "champ-001",
                        "latest_champion_freeze_date": "2026-04-01",
                    }
                }
            ]
        })
        rows = get_cross_artifact_correlation_v1(session, "es-1h-bear-sweep")
        # Must not raise
        json.dumps(rows)

    def test_no_file_system_reads(self) -> None:
        # Prove no fallback: when session returns empty, result is empty (not file read).
        session = FakeSession({GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER: []})
        rows = get_cross_artifact_correlation_v1(session, "es-1h-bear-sweep")
        assert rows == []

    def test_registered_in_query_view_registry(self) -> None:
        assert "get_cross_artifact_correlation_v1" in QUERY_VIEW_REGISTRY

    def test_cross_artifact_preset_exists(self) -> None:
        spec = resolve_preset("cross_artifact_correlation")
        assert spec.name == "cross_artifact_correlation"
        assert spec.requires_graph is True

    def test_cross_artifact_preset_requires_strategy_id(self) -> None:
        spec = resolve_preset("cross_artifact_correlation")
        errors = validate_params(spec, {})
        assert any("strategy_id" in e for e in errors)

    def test_cross_artifact_preset_routes_to_view(self) -> None:
        result_row = {
            "anchor_strategy_id": "es-1h-bear-sweep",
            "related_strategy_id": "nq-1h-bear-sweep",
        }
        service = FakeGraphQueryService(cross_artifact=[result_row])
        results = run_preset(
            "cross_artifact_correlation",
            {"strategy_id": "es-1h-bear-sweep"},
            service=service,
        )
        assert service.calls[0][0] == "get_cross_artifact_correlation_v1"
        assert service.calls[0][1] == {"strategy_id": "es-1h-bear-sweep"}
        assert results == [result_row]

    def test_cross_artifact_preset_empty_when_no_related_strategies(self) -> None:
        service = FakeGraphQueryService(cross_artifact=[])
        results = run_preset(
            "cross_artifact_correlation",
            {"strategy_id": "unique-strategy"},
            service=service,
        )
        assert results == []


# ---------------------------------------------------------------------------
# CrossArtifactRowV1 DTO
# ---------------------------------------------------------------------------

class TestCrossArtifactRowV1:
    def test_stable_json_keys(self) -> None:
        model = CrossArtifactRowV1(
            anchor_strategy_id="es-1h-bear-sweep",
            related_strategy_id="nq-1h-bear-sweep",
            instrument="NQ",
            timeframe="1H",
            direction="bear",
            logic_type="sweep",
            run_count=3,
            champion_count=1,
            latest_champion_id="champ-001",
            latest_champion_freeze_date="2026-04-01",
        )
        d = model.model_dump(mode="json")
        assert d["version"] == "v1"
        assert d["anchor_strategy_id"] == "es-1h-bear-sweep"
        assert d["related_strategy_id"] == "nq-1h-bear-sweep"

    def test_optional_fields_default_to_none(self) -> None:
        model = CrossArtifactRowV1(
            anchor_strategy_id="es-1h-bear-sweep",
            related_strategy_id="nq-1h-bear-sweep",
            instrument="NQ",
            timeframe="1H",
            direction="bear",
            logic_type="sweep",
        )
        d = model.model_dump(mode="json")
        assert d["latest_champion_id"] is None
        assert d["latest_champion_freeze_date"] is None
        assert d["run_count"] == 0
        assert d["champion_count"] == 0


# ---------------------------------------------------------------------------
# Preset catalog completeness
# ---------------------------------------------------------------------------

class TestPresetCatalogStory4:
    def test_five_presets_exist(self) -> None:
        assert set(PRESET_CATALOG) == {
            "recent_champions",
            "strategy_lineage",
            "pending_offline",
            "downstream_champions",
            "cross_artifact_correlation",
        }
