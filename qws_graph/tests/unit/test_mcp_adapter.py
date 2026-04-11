"""Unit tests for Story 3 MCP Read Adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.mcp_adapter import (
    TOOL_BINDINGS,
    McpError,
    McpReadAdapter,
    McpResult,
)

# ---------------------------------------------------------------------------
# Fake service
# ---------------------------------------------------------------------------

class FakeGraphQueryService:
    """Minimal duck-type for GraphQueryService."""

    def __init__(
        self,
        recent_champions: list[dict[str, Any]] | None = None,
        strategy_lineage: list[dict[str, Any]] | None = None,
        champion_details: dict[str, Any] | None = None,
        strategy_summary: dict[str, Any] | None = None,
        config_linkage: dict[str, Any] | None = None,
        run_history: list[dict[str, Any]] | None = None,
        raise_on: str | None = None,  # method name that should raise
    ) -> None:
        self._recent_champions = recent_champions or []
        self._strategy_lineage = strategy_lineage or []
        self._champion_details = champion_details
        self._strategy_summary = strategy_summary
        self._config_linkage = config_linkage
        self._run_history = run_history or []
        self._raise_on = raise_on
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _maybe_raise(self, name: str) -> None:
        if self._raise_on == name:
            raise ConnectionError(f"fake infra failure in {name}")

    def get_recent_champions_v1(self, limit: int = 20) -> list[dict[str, Any]]:
        self._maybe_raise("get_recent_champions_v1")
        self.calls.append(("get_recent_champions_v1", {"limit": limit}))
        return self._recent_champions[:limit]

    def get_strategy_lineage_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        self._maybe_raise("get_strategy_lineage_v1")
        self.calls.append(("get_strategy_lineage_v1", {"strategy_id": strategy_id}))
        return self._strategy_lineage

    def get_champion_details_v1(self, champion_id: str) -> dict[str, Any] | None:
        self._maybe_raise("get_champion_details_v1")
        self.calls.append(("get_champion_details_v1", {"champion_id": champion_id}))
        return self._champion_details

    def get_strategy_summary_v1(self, strategy_id: str) -> dict[str, Any] | None:
        self._maybe_raise("get_strategy_summary_v1")
        self.calls.append(("get_strategy_summary_v1", {"strategy_id": strategy_id}))
        return self._strategy_summary

    def get_config_linkage_v1(self, run_id: str) -> dict[str, Any] | None:
        self._maybe_raise("get_config_linkage_v1")
        self.calls.append(("get_config_linkage_v1", {"run_id": run_id}))
        return self._config_linkage

    def get_run_history_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        self._maybe_raise("get_run_history_v1")
        self.calls.append(("get_run_history_v1", {"strategy_id": strategy_id}))
        return self._run_history

    def close(self) -> None:
        pass


def _adapter(service: FakeGraphQueryService) -> McpReadAdapter:
    return McpReadAdapter(service)


# ---------------------------------------------------------------------------
# McpResult envelope
# ---------------------------------------------------------------------------

class TestMcpResult:
    def test_success_to_dict(self) -> None:
        result = McpResult(ok=True, data={"champion_id": "c1"})
        d = result.to_dict()
        assert d == {"ok": True, "data": {"champion_id": "c1"}, "error": None}

    def test_error_to_dict(self) -> None:
        result = McpResult(
            ok=False,
            data=None,
            error=McpError(code="INFRA_ERROR", message="connection refused"),
        )
        d = result.to_dict()
        assert d == {
            "ok": False,
            "data": None,
            "error": {"code": "INFRA_ERROR", "message": "connection refused"},
        }

    def test_empty_list_success(self) -> None:
        result = McpResult(ok=True, data=[])
        d = result.to_dict()
        assert d["ok"] is True
        assert d["data"] == []
        assert d["error"] is None

    def test_not_found_representation(self) -> None:
        result = McpResult(ok=True, data=None)
        d = result.to_dict()
        assert d["ok"] is True
        assert d["data"] is None
        assert d["error"] is None

    def test_to_dict_keys_are_stable(self) -> None:
        result = McpResult(ok=True, data=[])
        assert set(result.to_dict()) == {"ok", "data", "error"}

    def test_error_dict_keys_are_stable(self) -> None:
        result = McpResult(
            ok=False,
            data=None,
            error=McpError(code="INVALID_PARAMS", message="bad"),
        )
        assert set(result.to_dict()["error"]) == {"code", "message"}


# ---------------------------------------------------------------------------
# TOOL_BINDINGS
# ---------------------------------------------------------------------------

class TestToolBindings:
    def test_all_three_tools_bound(self) -> None:
        assert set(TOOL_BINDINGS) == {
            "get_recent_champions",
            "get_strategy_lineage",
            "get_context_neighborhood",
        }

    def test_bindings_reference_query_view_names(self) -> None:
        from research.graph.query import QUERY_VIEW_REGISTRY
        for tool, view_name in TOOL_BINDINGS.items():
            assert view_name in QUERY_VIEW_REGISTRY, (
                f"tool {tool!r} is bound to {view_name!r} which is not in QUERY_VIEW_REGISTRY"
            )


# ---------------------------------------------------------------------------
# get_recent_champions
# ---------------------------------------------------------------------------

class TestGetRecentChampions:
    def test_success_returns_list(self) -> None:
        service = FakeGraphQueryService(
            recent_champions=[{"champion_id": "c1"}, {"champion_id": "c2"}]
        )
        result = _adapter(service).get_recent_champions()
        assert result.ok is True
        assert result.data == [{"champion_id": "c1"}, {"champion_id": "c2"}]
        assert result.error is None

    def test_empty_graph_returns_empty_list(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_recent_champions()
        assert result.ok is True
        assert result.data == []

    def test_limit_forwarded_to_view(self) -> None:
        service = FakeGraphQueryService(
            recent_champions=[{"champion_id": f"c{i}"} for i in range(10)]
        )
        _adapter(service).get_recent_champions(limit=3)
        assert service.calls[0] == ("get_recent_champions_v1", {"limit": 3})

    def test_default_limit_is_20(self) -> None:
        service = FakeGraphQueryService()
        _adapter(service).get_recent_champions()
        assert service.calls[0][1]["limit"] == 20

    def test_invalid_limit_returns_invalid_params_error(self) -> None:
        service = FakeGraphQueryService()
        result = _adapter(service).get_recent_champions(limit=0)
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "INVALID_PARAMS"
        assert service.calls == []  # no graph call made

    def test_negative_limit_returns_invalid_params_error(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_recent_champions(limit=-1)
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_infra_error_returns_infra_error_envelope(self) -> None:
        service = FakeGraphQueryService(raise_on="get_recent_champions_v1")
        result = _adapter(service).get_recent_champions()
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "INFRA_ERROR"
        assert "fake infra failure" in result.error.message

    def test_no_filesystem_calls(self) -> None:
        # Verifying that service is not bypassed — adapter calls service method, not files.
        # If service raises, result is INFRA_ERROR (not a file fallback).
        service = FakeGraphQueryService(raise_on="get_recent_champions_v1")
        result = _adapter(service).get_recent_champions()
        assert result.ok is False  # still INFRA_ERROR, no data from fallback


# ---------------------------------------------------------------------------
# get_strategy_lineage
# ---------------------------------------------------------------------------

class TestGetStrategyLineage:
    def test_success_returns_lineage_rows(self) -> None:
        rows = [{"champion_id": "c1", "strategy_id": "es-1h-bear-sweep"}]
        service = FakeGraphQueryService(strategy_lineage=rows)
        result = _adapter(service).get_strategy_lineage("es-1h-bear-sweep")
        assert result.ok is True
        assert result.data == rows

    def test_unknown_strategy_returns_empty_list_not_error(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_strategy_lineage("nonexistent")
        assert result.ok is True
        assert result.data == []
        assert result.error is None

    def test_strategy_id_forwarded_to_view(self) -> None:
        service = FakeGraphQueryService()
        _adapter(service).get_strategy_lineage("es-1h-bear-sweep")
        assert service.calls[0] == (
            "get_strategy_lineage_v1",
            {"strategy_id": "es-1h-bear-sweep"},
        )

    def test_empty_strategy_id_returns_invalid_params(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_strategy_lineage("")
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_infra_error_returns_infra_error_envelope(self) -> None:
        service = FakeGraphQueryService(raise_on="get_strategy_lineage_v1")
        result = _adapter(service).get_strategy_lineage("es-1h-bear-sweep")
        assert result.ok is False
        assert result.error.code == "INFRA_ERROR"

    def test_no_filesystem_fallback_on_infra_error(self) -> None:
        service = FakeGraphQueryService(raise_on="get_strategy_lineage_v1")
        result = _adapter(service).get_strategy_lineage("es-1h-bear-sweep")
        assert result.ok is False
        assert result.data is None


# ---------------------------------------------------------------------------
# get_context_neighborhood
# ---------------------------------------------------------------------------

_CHAMPION = {
    "champion_id": "champ-001",
    "strategy_id": "es-1h-bear-sweep",
    "freeze_date": "2026-04-01",
    "oos_status": "pending",
    "fragilities": [],
    "artifact_path": "results/champ.md",
    "pivot_from_run_id": "run-001",
    "metrics_summary": {},
    "version": "v1",
}

_STRATEGY = {
    "strategy_id": "es-1h-bear-sweep",
    "instrument": "ES",
    "timeframe": "1H",
    "direction": "bear",
    "logic_type": "sweep",
    "run_count": 3,
    "champion_count": 1,
    "version": "v1",
}

_CONFIG = {
    "strategy_id": "es-1h-bear-sweep",
    "run_id": "run-001",
    "config_id": "cfg-001",
    "params_json": {"fast_ema": 9},
    "risk_params": None,
    "version": "v1",
}


class TestGetContextNeighborhood:
    def test_success_returns_all_five_parts(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            config_linkage=_CONFIG,
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is True
        assert result.data["champion"]["champion_id"] == "champ-001"
        assert result.data["strategy"]["strategy_id"] == "es-1h-bear-sweep"
        assert result.data["pivot_config"]["config_id"] == "cfg-001"
        assert result.data["recent_runs"] == []
        assert result.data["runs_capped"] is False

    def test_not_found_returns_ok_true_data_none(self) -> None:
        service = FakeGraphQueryService(champion_details=None)
        result = _adapter(service).get_context_neighborhood("missing-champ")
        assert result.ok is True
        assert result.data is None
        assert result.error is None

    def test_no_pivot_run_pivot_config_is_none(self) -> None:
        champion_no_pivot = {**_CHAMPION, "pivot_from_run_id": None}
        service = FakeGraphQueryService(
            champion_details=champion_no_pivot,
            strategy_summary=_STRATEGY,
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is True
        assert result.data["pivot_config"] is None
        # no config linkage call made
        assert not any(c[0] == "get_config_linkage_v1" for c in service.calls)

    def test_missing_pivot_config_from_graph_is_returned_as_none(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            config_linkage=None,  # pivot run exists but has no config
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is True
        assert result.data["pivot_config"] is None

    def test_data_shape_keys_are_stable(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            config_linkage=_CONFIG,
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert set(result.data) == {
            "champion",
            "strategy",
            "pivot_config",
            "recent_runs",
            "runs_capped",
        }

    def test_empty_champion_id_returns_invalid_params(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_context_neighborhood("")
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_infra_error_on_champion_lookup_returns_infra_error(self) -> None:
        service = FakeGraphQueryService(raise_on="get_champion_details_v1")
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is False
        assert result.error.code == "INFRA_ERROR"

    def test_infra_error_on_strategy_lookup_returns_infra_error(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            raise_on="get_strategy_summary_v1",
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is False
        assert result.error.code == "INFRA_ERROR"

    def test_view_function_calls_are_by_stable_name(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            config_linkage=_CONFIG,
        )
        _adapter(service).get_context_neighborhood("champ-001")
        names = [c[0] for c in service.calls]
        assert "get_champion_details_v1" in names
        assert "get_strategy_summary_v1" in names
        assert "get_config_linkage_v1" in names
        assert "get_run_history_v1" in names

    def test_max_runs_default_is_50(self) -> None:
        runs = [{"run_id": f"r{i}"} for i in range(60)]
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            run_history=runs,
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        assert result.ok is True
        assert len(result.data["recent_runs"]) == 50
        assert result.data["runs_capped"] is True

    def test_max_runs_param_respected(self) -> None:
        runs = [{"run_id": f"r{i}"} for i in range(10)]
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            run_history=runs,
        )
        result = _adapter(service).get_context_neighborhood("champ-001", max_runs=5)
        assert result.ok is True
        assert len(result.data["recent_runs"]) == 5
        assert result.data["runs_capped"] is True

    def test_runs_capped_false_when_under_limit(self) -> None:
        runs = [{"run_id": f"r{i}"} for i in range(3)]
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            run_history=runs,
        )
        result = _adapter(service).get_context_neighborhood("champ-001", max_runs=10)
        assert result.data["runs_capped"] is False
        assert len(result.data["recent_runs"]) == 3

    def test_max_runs_zero_returns_invalid_params(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_context_neighborhood(
            "champ-001", max_runs=0
        )
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_max_runs_201_returns_invalid_params(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_context_neighborhood(
            "champ-001", max_runs=201
        )
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_max_runs_200_is_accepted(self) -> None:
        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
        )
        result = _adapter(service).get_context_neighborhood("champ-001", max_runs=200)
        assert result.ok is True

    def test_max_runs_invalid_type_returns_invalid_params(self) -> None:
        result = _adapter(FakeGraphQueryService()).get_context_neighborhood(
            "champ-001", max_runs="50"  # type: ignore[arg-type]
        )
        assert result.ok is False
        assert result.error.code == "INVALID_PARAMS"

    def test_no_filesystem_fallback_when_champion_missing(self) -> None:
        # Champion not in graph → data=None, no file lookup attempted.
        service = FakeGraphQueryService(champion_details=None)
        result = _adapter(service).get_context_neighborhood("missing")
        assert result.ok is True
        assert result.data is None
        # Only one call was made
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_champion_details_v1"


# ---------------------------------------------------------------------------
# Deterministic JSON compatibility
# ---------------------------------------------------------------------------

class TestJsonCompatibility:
    def test_to_dict_is_json_serializable(self) -> None:
        import json

        service = FakeGraphQueryService(
            recent_champions=[{"champion_id": "c1", "version": "v1"}]
        )
        result = _adapter(service).get_recent_champions()
        # Must not raise
        serialized = json.dumps(result.to_dict())
        roundtripped = json.loads(serialized)
        assert roundtripped["ok"] is True
        assert roundtripped["data"][0]["champion_id"] == "c1"

    def test_error_envelope_is_json_serializable(self) -> None:
        import json

        service = FakeGraphQueryService(raise_on="get_recent_champions_v1")
        result = _adapter(service).get_recent_champions()
        serialized = json.dumps(result.to_dict())
        roundtripped = json.loads(serialized)
        assert roundtripped["ok"] is False
        assert roundtripped["error"]["code"] == "INFRA_ERROR"

    def test_context_neighborhood_to_dict_is_json_serializable(self) -> None:
        import json

        service = FakeGraphQueryService(
            champion_details=_CHAMPION,
            strategy_summary=_STRATEGY,
            config_linkage=_CONFIG,
        )
        result = _adapter(service).get_context_neighborhood("champ-001")
        serialized = json.dumps(result.to_dict())
        assert json.loads(serialized)["ok"] is True
