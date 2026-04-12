"""Unit tests for Story 2 qw query presets and CLI routing."""

from __future__ import annotations

import argparse
import json
from typing import Any
from unittest.mock import patch

import pytest
from research.graph.cli import cmd_query
from research.graph.query_presets import (
    PRESET_CATALOG,
    PresetSpec,
    _extract_artifact_path,
    resolve_preset,
    run_preset,
    validate_params,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeGraphQueryService:
    """Minimal duck-type for GraphQueryService used in preset routing tests."""

    def __init__(
        self,
        recent_champions: list[dict[str, Any]] | None = None,
        strategy_lineage: list[dict[str, Any]] | None = None,
        run_history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._recent_champions = recent_champions or []
        self._strategy_lineage = strategy_lineage or []
        self._run_history = run_history or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_recent_champions_v1(self, limit: int = 20) -> list[dict[str, Any]]:
        self.calls.append(("get_recent_champions_v1", {"limit": limit}))
        return self._recent_champions[:limit]

    def get_strategy_lineage_v1(self, strategy_id: str, depth: int = 1) -> list[dict[str, Any]]:
        self.calls.append(("get_strategy_lineage_v1", {"strategy_id": strategy_id, "depth": depth}))
        return self._strategy_lineage

    def get_run_history_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        self.calls.append(("get_run_history_v1", {"strategy_id": strategy_id}))
        return self._run_history

    def get_portfolio_alpha_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_portfolio_alpha_v1", {}))
        return [{"champion_count": 1, "total_return": 0.1, "avg_sharpe": 4.5, "strategies": ["s1"]}]

    def get_fragility_report_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_fragility_report_v1", {}))
        return [{"strategy_id": "s1", "champion_id": "c1", "fragilities": ["regime risk"]}]

    def get_staleness_report_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_staleness_report_v1", {}))
        return [
            {
                "champion_id": "c1", "strategy_id": "s1",
                "freeze_date": "2025-01-01", "days_stale": 90,
            },
        ]

    def get_instrument_concentration_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_instrument_concentration_v1", {}))
        return [{"instrument": "ES", "champion_count": 3, "total_return": 0.45}]

    def get_list_oos_pending_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_list_oos_pending_v1", {}))
        return [
            {
                "champion_id": "c1",
                "strategy_id": "es-1h-bear-sweep",
                "freeze_date": "2026-01-01",
                "metrics_sharpe": 3.5,
                "metrics_total_trades": 45,
                "days_pending": 97,
            }
        ]

    def get_list_aborted_v1(self) -> list[dict[str, Any]]:
        self.calls.append(("get_list_aborted_v1", {}))
        return [
            {
                "strategy_id": "cl-1h-bear-sweep",
                "instrument": "CL",
                "direction": "bear",
                "logic_type": "liquidity_sweep",
                "abort_reason": "Sharpe below threshold after 3 runs",
                "aborted_at": "2025-12-01",
            }
        ]

    def get_promotion_candidates_v1(
        self,
        min_sharpe: float = 2.0,
        min_profit_factor: float = 1.3,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "get_promotion_candidates_v1",
                {"min_sharpe": min_sharpe, "min_profit_factor": min_profit_factor},
            )
        )
        return [
            {
                "run_id": "run-001",
                "strategy_id": "es-1h-bear-sweep",
                "sharpe": 2.8,
                "tier": "professional",
                "profit_factor": 1.5,
                "total_trades": 42,
                "active_window_frequency": 0.12,
                "duty_cycle": 0.35,
                "evidence_score": 18.14,
                "ingested_at": "2026-03-01T10:00:00",
            }
        ]

    def close(self) -> None:
        pass


def _make_query_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "name": "pending_offline",
        "json": False,
        "param": None,
        "repo_root": None,
        "timeout_seconds": 3,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# PRESET_CATALOG
# ---------------------------------------------------------------------------

class TestPresetCatalog:
    def test_core_presets_present(self) -> None:
        # Checks that Story 2 presets are present; Story 4 adds more (see test_lineage_queries.py).
        presets = {"recent_champions", "strategy_lineage", "run_history", "pending_offline"}
        assert presets.issubset(set(PRESET_CATALOG))

    def test_preset_specs_have_stable_fields(self) -> None:
        for name, spec in PRESET_CATALOG.items():
            assert isinstance(spec, PresetSpec)
            assert spec.name == name
            assert spec.description

    def test_pending_offline_does_not_require_graph(self) -> None:
        assert PRESET_CATALOG["pending_offline"].requires_graph is False

    def test_recent_champions_requires_graph(self) -> None:
        assert PRESET_CATALOG["recent_champions"].requires_graph is True

    def test_strategy_lineage_requires_graph(self) -> None:
        assert PRESET_CATALOG["strategy_lineage"].requires_graph is True


# ---------------------------------------------------------------------------
# resolve_preset
# ---------------------------------------------------------------------------

class TestResolvePreset:
    def test_known_presets_resolve(self) -> None:
        for name in ["recent_champions", "strategy_lineage", "run_history", "pending_offline"]:
            spec = resolve_preset(name)
            assert spec.name == name

    def test_unknown_preset_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown preset"):
            resolve_preset("nonexistent_preset")

    def test_unknown_preset_message_lists_available(self) -> None:
        with pytest.raises(ValueError, match="recent_champions"):
            resolve_preset("nonexistent_preset")

    def test_error_message_is_deterministic(self) -> None:
        try:
            resolve_preset("bad")
        except ValueError as exc:
            msg = str(exc)
        try:
            resolve_preset("bad")
        except ValueError as exc2:
            assert str(exc2) == msg


# ---------------------------------------------------------------------------
# validate_params
# ---------------------------------------------------------------------------

class TestValidateParams:
    def test_recent_champions_no_params_valid(self) -> None:
        spec = resolve_preset("recent_champions")
        assert validate_params(spec, {}) == []

    def test_recent_champions_with_limit_valid(self) -> None:
        spec = resolve_preset("recent_champions")
        assert validate_params(spec, {"limit": "5"}) == []

    def test_recent_champions_unknown_param_rejected(self) -> None:
        spec = resolve_preset("recent_champions")
        errors = validate_params(spec, {"bogus": "val"})
        assert any("unknown param" in e for e in errors)

    def test_strategy_lineage_missing_strategy_id(self) -> None:
        spec = resolve_preset("strategy_lineage")
        errors = validate_params(spec, {})
        assert any("strategy_id" in e for e in errors)

    def test_strategy_lineage_valid(self) -> None:
        spec = resolve_preset("strategy_lineage")
        assert validate_params(spec, {"strategy_id": "es-1h-bear-sweep"}) == []

    def test_strategy_lineage_unknown_extra_param(self) -> None:
        spec = resolve_preset("strategy_lineage")
        errors = validate_params(spec, {"strategy_id": "es-1h-bear-sweep", "extra": "x"})
        assert any("unknown param" in e for e in errors)

    def test_pending_offline_no_params_valid(self) -> None:
        spec = resolve_preset("pending_offline")
        assert validate_params(spec, {}) == []

    def test_run_history_requires_strategy_id(self) -> None:
        spec = resolve_preset("run_history")
        errors = validate_params(spec, {})
        assert any("strategy_id" in e for e in errors)


# ---------------------------------------------------------------------------
# run_preset — pending_offline (no graph required)
# ---------------------------------------------------------------------------

class TestRunPresetPendingOffline:
    def test_empty_pending_dir_returns_empty_list(self, tmp_path: Path) -> None:
        results = run_preset("pending_offline", {}, repo_root=tmp_path)
        assert results == []

    def test_missing_pending_dir_returns_empty_list(self, tmp_path: Path) -> None:
        results = run_preset("pending_offline", {}, repo_root=tmp_path / "nonexistent")
        assert results == []

    def test_pending_baseline_csv_listed(self, tmp_path: Path) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        payload = {
            "kind": "baseline_csv",
            "runs": [{"artifact_path": "results/es_1h.csv", "run_id": "run-001"}],
        }
        (pending / "run-001.json").write_text(json.dumps(payload))

        results = run_preset("pending_offline", {}, repo_root=tmp_path)

        assert len(results) == 1
        assert results[0]["id"] == "run-001"
        assert results[0]["kind"] == "baseline_csv"
        assert results[0]["artifact_path"] == "results/es_1h.csv"

    def test_pending_champion_md_listed(self, tmp_path: Path) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        payload = {
            "kind": "champion_md",
            "champion": {"champion_id": "champ-001", "artifact_path": "results/champ.md"},
        }
        (pending / "champ-001.json").write_text(json.dumps(payload))

        results = run_preset("pending_offline", {}, repo_root=tmp_path)

        assert results[0]["artifact_path"] == "results/champ.md"

    def test_unreadable_pending_file_returns_error_entry(self, tmp_path: Path) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        (pending / "bad-001.json").write_text("not json{{{")

        results = run_preset("pending_offline", {}, repo_root=tmp_path)

        assert results[0]["id"] == "bad-001"
        assert results[0]["error"] == "unreadable"

    def test_multiple_files_sorted_by_name(self, tmp_path: Path) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        for name in ["run-003", "run-001", "run-002"]:
            (pending / f"{name}.json").write_text(json.dumps({"kind": "baseline_csv", "runs": []}))

        results = run_preset("pending_offline", {}, repo_root=tmp_path)
        ids = [r["id"] for r in results]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# run_preset — graph-backed presets (fake service)
# ---------------------------------------------------------------------------

class TestRunPresetRecentChampions:
    def test_routes_to_get_recent_champions_v1(self) -> None:
        service = FakeGraphQueryService(recent_champions=[{"champion_id": "c1"}])
        results = run_preset("recent_champions", {}, service=service)
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_recent_champions_v1"
        assert results == [{"champion_id": "c1"}]

    def test_limit_param_passed_through(self) -> None:
        service = FakeGraphQueryService(
            recent_champions=[{"champion_id": f"c{i}"} for i in range(10)]
        )
        run_preset("recent_champions", {"limit": "3"}, service=service)
        assert service.calls[0][1]["limit"] == 3

    def test_default_limit_is_20(self) -> None:
        service = FakeGraphQueryService()
        run_preset("recent_champions", {}, service=service)
        assert service.calls[0][1]["limit"] == 20

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("recent_champions", {}, service=None)


class TestRunPresetStrategyLineage:
    def test_routes_to_get_strategy_lineage_v1(self) -> None:
        service = FakeGraphQueryService(strategy_lineage=[{"champion_id": "c1"}])
        results = run_preset(
            "strategy_lineage", {"strategy_id": "es-1h-bear-sweep"}, service=service
        )
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_strategy_lineage_v1"
        assert service.calls[0][1]["strategy_id"] == "es-1h-bear-sweep"
        assert results == [{"champion_id": "c1"}]

    def test_missing_strategy_id_raises_value_error(self) -> None:
        service = FakeGraphQueryService()
        with pytest.raises(ValueError, match="missing required param"):
            run_preset("strategy_lineage", {}, service=service)

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("strategy_lineage", {"strategy_id": "es-1h-bear-sweep"}, service=None)


class TestRunPresetRunHistory:
    def test_routes_to_get_run_history_v1(self) -> None:
        service = FakeGraphQueryService(run_history=[{"run_id": "r1", "curator_note": "ok"}])
        results = run_preset("run_history", {"strategy_id": "es-1h-bear-sweep"}, service=service)
        assert service.calls[0][0] == "get_run_history_v1"
        assert results[0]["curator_note"] == "ok"


class TestRunPresetUnknown:
    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown preset"):
            run_preset("no_such_preset", {})


# ---------------------------------------------------------------------------
# _extract_artifact_path
# ---------------------------------------------------------------------------

class TestExtractArtifactPath:
    def test_runs_list(self) -> None:
        payload = {"kind": "baseline_csv", "runs": [{"artifact_path": "a/b.csv"}]}
        assert _extract_artifact_path(payload) == "a/b.csv"

    def test_champion_dict(self) -> None:
        payload = {"kind": "champion_md", "champion": {"artifact_path": "c/d.md"}}
        assert _extract_artifact_path(payload) == "c/d.md"

    def test_blob_dict(self) -> None:
        payload = {"kind": "tracker_md", "blob": {"artifact_path": "e/f.md"}}
        assert _extract_artifact_path(payload) == "e/f.md"

    def test_empty_payload_returns_none(self) -> None:
        assert _extract_artifact_path({}) is None

    def test_empty_runs_list_returns_none(self) -> None:
        assert _extract_artifact_path({"runs": []}) is None


# ---------------------------------------------------------------------------
# cmd_query — CLI orchestration
# ---------------------------------------------------------------------------

class TestCmdQueryErrors:
    def test_unknown_preset_returns_exit_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_query_args(name="does_not_exist")
        exit_code = cmd_query(args)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "unknown preset" in captured.err

    def test_bad_param_format_returns_exit_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_query_args(
            name="recent_champions",
            param=["no_equals_sign"],
            repo_root=str(tmp_path),
        )
        exit_code = cmd_query(args)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "--param must be key=value" in captured.err

    def test_missing_required_param_returns_exit_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # strategy_lineage requires strategy_id — but NeoConnector will be hit first.
        # Patch it so param validation is tested independently.
        args = _make_query_args(name="strategy_lineage", param=None, repo_root=str(tmp_path))
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = True
            with patch("research.graph.cli.GraphQueryService") as mock_svc_cls:
                mock_svc_cls.from_env.return_value = FakeGraphQueryService()
                exit_code = cmd_query(args)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "strategy_id" in captured.err


class TestCmdQueryPendingOffline:
    def test_pending_offline_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        payload = {"kind": "baseline_csv", "runs": [{"artifact_path": "results/es.csv"}]}
        (pending / "run-001.json").write_text(json.dumps(payload))

        args = _make_query_args(name="pending_offline", repo_root=str(tmp_path))
        exit_code = cmd_query(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        row = json.loads(captured.out.strip())
        assert row["id"] == "run-001"

    def test_pending_offline_json_output_shape_is_stable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pending = tmp_path / ".qws" / "pending"
        pending.mkdir(parents=True)
        payload = {"kind": "champion_md", "champion": {"artifact_path": "r/c.md"}}
        (pending / "champ-001.json").write_text(json.dumps(payload))

        args = _make_query_args(
            name="pending_offline", repo_root=str(tmp_path), **{"json": True}
        )
        exit_code = cmd_query(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # Stable shape: {"preset": str, "results": list}
        assert output["preset"] == "pending_offline"
        assert isinstance(output["results"], list)
        assert output["results"][0]["id"] == "champ-001"

    def test_empty_results_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_query_args(name="pending_offline", repo_root=str(tmp_path))
        exit_code = cmd_query(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No results" in captured.out


class TestCmdQueryGraphBacked:
    def test_recent_champions_json_output_shape(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_service = FakeGraphQueryService(
            recent_champions=[
                {
                    "champion_id": "c1", "strategy_id": "es-1h-bear-sweep",
                    "freeze_date": "2026-04-01",
                }
            ]
        )
        args = _make_query_args(
            name="recent_champions", repo_root=str(tmp_path), **{"json": True}
        )
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = True
            with patch("research.graph.cli.GraphQueryService") as mock_svc_cls:
                mock_svc_cls.from_env.return_value = fake_service
                exit_code = cmd_query(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["preset"] == "recent_champions"
        assert output["results"][0]["champion_id"] == "c1"

    def test_strategy_lineage_routes_correctly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        lineage_row = {"champion_id": "c1", "strategy_id": "es-1h-bear-sweep"}
        fake_service = FakeGraphQueryService(strategy_lineage=[lineage_row])

        args = _make_query_args(
            name="strategy_lineage",
            param=["strategy_id=es-1h-bear-sweep"],
            repo_root=str(tmp_path),
            **{"json": True},
        )
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = True
            with patch("research.graph.cli.GraphQueryService") as mock_svc_cls:
                mock_svc_cls.from_env.return_value = fake_service
                exit_code = cmd_query(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["preset"] == "strategy_lineage"
        assert output["results"][0]["champion_id"] == "c1"
        assert fake_service.calls[0][1]["strategy_id"] == "es-1h-bear-sweep"

    def test_neo4j_unavailable_returns_exit_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_query_args(name="recent_champions", repo_root=str(tmp_path))
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = False
            exit_code = cmd_query(args)

        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Neo4j unavailable" in captured.err

    def test_run_history_text_output_includes_timestamp_trades_sharpe_drawdown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_service = FakeGraphQueryService(
            run_history=[
                {
                    "run_id": "run-001",
                    "timestamp": "2026-04-01T10:00:00Z",
                    "sharpe": 1.23,
                    "max_drawdown": -7.8,
                    "total_trades": 12,
                    "curator_note": "Strong expectancy",
                }
            ]
        )
        args = _make_query_args(
            name="run_history",
            param=["strategy_id=es-1h-bear-sweep"],
            repo_root=str(tmp_path),
            **{"json": False},
        )
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = True
            with patch("research.graph.cli.GraphQueryService") as mock_svc_cls:
                mock_svc_cls.from_env.return_value = fake_service
                exit_code = cmd_query(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        row = json.loads(captured.out.strip())
        assert row["timestamp"] == "2026-04-01T10:00:00Z"
        assert row["sharpe"] == 1.23
        assert row["max_drawdown"] == -7.8
        assert row["total_trades"] == 12
        assert row["curator_note"] == "Strong expectancy"

    def test_run_history_shortcut_flag_routes_to_preset(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_service = FakeGraphQueryService(run_history=[
            {"run_id": "run-001", "sharpe": 1.1, "max_drawdown": -5.0, "curator_note": None},
        ])
        args = _make_query_args(
            name=None,
            param=["strategy_id=es-1h-bear-sweep"],
            repo_root=str(tmp_path),
            **{"run_history": True},
        )
        with patch("research.graph.cli.NeoConnector") as mock_connector_cls:
            mock_connector_cls.return_value.is_available.return_value = True
            with patch("research.graph.cli.GraphQueryService") as mock_svc_cls:
                mock_svc_cls.from_env.return_value = fake_service
                exit_code = cmd_query(args)

        assert exit_code == 0
        assert fake_service.calls[0][0] == "get_run_history_v1"



# ---------------------------------------------------------------------------
# run_preset — new analytical presets (QWS-0302)
# ---------------------------------------------------------------------------

class TestRunPresetPortfolioAlpha:
    def test_routes_to_get_portfolio_alpha_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("portfolio_alpha", {}, service=service)
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_portfolio_alpha_v1"
        assert results[0]["avg_sharpe"] == 4.5

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("portfolio_alpha", {}, service=None)

    def test_unknown_param_rejected(self) -> None:
        spec = resolve_preset("portfolio_alpha")
        errors = validate_params(spec, {"limit": "5"})
        assert any("unknown param" in e for e in errors)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("portfolio_alpha")
        assert validate_params(spec, {}) == []


class TestRunPresetFragilityReport:
    def test_routes_to_get_fragility_report_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("fragility_report", {}, service=service)
        assert service.calls[0][0] == "get_fragility_report_v1"
        assert results[0]["champion_id"] == "c1"

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("fragility_report", {}, service=None)


class TestRemovedPresetTraceChampion:
    def test_trace_champion_raises_unknown_preset(self) -> None:
        with pytest.raises(ValueError, match="unknown preset"):
            run_preset("trace_champion", {"champion_id": "abc123"})

    def test_trace_champion_not_in_catalog(self) -> None:
        assert "trace_champion" not in PRESET_CATALOG


class TestRunPresetStalenessReport:
    def test_routes_to_get_staleness_report_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("staleness_report", {}, service=service)
        assert service.calls[0][0] == "get_staleness_report_v1"
        assert results[0]["days_stale"] == 90

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("staleness_report", {}, service=None)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("staleness_report")
        assert validate_params(spec, {}) == []

    def test_unknown_param_rejected(self) -> None:
        spec = resolve_preset("staleness_report")
        errors = validate_params(spec, {"limit": "5"})
        assert any("unknown param" in e for e in errors)


class TestRunPresetInstrumentConcentration:
    def test_routes_to_get_instrument_concentration_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("instrument_concentration", {}, service=service)
        assert service.calls[0][0] == "get_instrument_concentration_v1"
        assert results[0]["instrument"] == "ES"

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("instrument_concentration", {}, service=None)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("instrument_concentration")
        assert validate_params(spec, {}) == []


class TestRemovedPresetRankByEvidence:
    def test_rank_by_evidence_raises_unknown_preset(self) -> None:
        with pytest.raises(ValueError, match="unknown preset"):
            run_preset("rank_by_evidence", {"strategy_id": "cl-1h-bear"})

    def test_rank_by_evidence_not_in_catalog(self) -> None:
        assert "rank_by_evidence" not in PRESET_CATALOG


class TestNewPresetCatalogEntries:
    def test_analytical_presets_present_in_catalog(self) -> None:
        assert {
            "portfolio_alpha", "fragility_report",
            "staleness_report", "instrument_concentration",
        }.issubset(set(PRESET_CATALOG))

    def test_workflow_presets_present_in_catalog(self) -> None:
        assert {
            "list_oos_pending", "list_aborted", "promotion_candidates",
        }.issubset(set(PRESET_CATALOG))

    def test_all_graph_presets_require_graph(self) -> None:
        for name in ("portfolio_alpha", "fragility_report", "staleness_report",
                     "instrument_concentration", "list_oos_pending", "list_aborted",
                     "promotion_candidates"):
            assert PRESET_CATALOG[name].requires_graph is True

    def test_promotion_candidates_has_optional_params(self) -> None:
        spec = resolve_preset("promotion_candidates")
        param_names = {p.name for p in spec.params}
        assert param_names == {"min_sharpe", "min_profit_factor"}

    def test_promotion_candidates_params_are_optional(self) -> None:
        spec = resolve_preset("promotion_candidates")
        required = {p.name for p in spec.params if p.required}
        assert required == set()


# ---------------------------------------------------------------------------
# run_preset — QWS-0406 workflow presets
# ---------------------------------------------------------------------------

class TestRunPresetListOosPending:
    def test_routes_to_get_list_oos_pending_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("list_oos_pending", {}, service=service)
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_list_oos_pending_v1"
        assert results[0]["champion_id"] == "c1"

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("list_oos_pending", {}, service=None)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("list_oos_pending")
        assert validate_params(spec, {}) == []

    def test_unknown_param_rejected(self) -> None:
        spec = resolve_preset("list_oos_pending")
        errors = validate_params(spec, {"limit": "5"})
        assert any("unknown param" in e for e in errors)

    def test_empty_result_returned_gracefully(self) -> None:
        class EmptyService(FakeGraphQueryService):
            def get_list_oos_pending_v1(self) -> list[dict[str, Any]]:
                self.calls.append(("get_list_oos_pending_v1", {}))
                return []

        service = EmptyService()
        results = run_preset("list_oos_pending", {}, service=service)
        assert results == []

    def test_output_contains_expected_fields(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("list_oos_pending", {}, service=service)
        row = results[0]
        assert {"champion_id", "strategy_id", "freeze_date", "metrics_sharpe",
                "metrics_total_trades", "days_pending"}.issubset(row.keys())


class TestRunPresetListAborted:
    def test_routes_to_get_list_aborted_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("list_aborted", {}, service=service)
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_list_aborted_v1"
        assert results[0]["strategy_id"] == "cl-1h-bear-sweep"

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("list_aborted", {}, service=None)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("list_aborted")
        assert validate_params(spec, {}) == []

    def test_unknown_param_rejected(self) -> None:
        spec = resolve_preset("list_aborted")
        errors = validate_params(spec, {"instrument": "CL"})
        assert any("unknown param" in e for e in errors)

    def test_empty_result_returned_gracefully(self) -> None:
        class EmptyService(FakeGraphQueryService):
            def get_list_aborted_v1(self) -> list[dict[str, Any]]:
                self.calls.append(("get_list_aborted_v1", {}))
                return []

        service = EmptyService()
        results = run_preset("list_aborted", {}, service=service)
        assert results == []

    def test_output_contains_expected_fields(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("list_aborted", {}, service=service)
        row = results[0]
        assert {"strategy_id", "instrument", "direction", "logic_type",
                "abort_reason", "aborted_at"}.issubset(row.keys())


class TestRunPresetPromotionCandidates:
    def test_routes_to_get_promotion_candidates_v1(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("promotion_candidates", {}, service=service)
        assert len(service.calls) == 1
        assert service.calls[0][0] == "get_promotion_candidates_v1"
        assert results[0]["run_id"] == "run-001"

    def test_default_params_passed_through(self) -> None:
        service = FakeGraphQueryService()
        run_preset("promotion_candidates", {}, service=service)
        call_kwargs = service.calls[0][1]
        assert call_kwargs["min_sharpe"] == 2.0
        assert call_kwargs["min_profit_factor"] == 1.3

    def test_min_sharpe_param_passed_through(self) -> None:
        service = FakeGraphQueryService()
        run_preset("promotion_candidates", {"min_sharpe": "2.5"}, service=service)
        assert service.calls[0][1]["min_sharpe"] == 2.5

    def test_min_profit_factor_param_passed_through(self) -> None:
        service = FakeGraphQueryService()
        run_preset("promotion_candidates", {"min_profit_factor": "1.5"}, service=service)
        assert service.calls[0][1]["min_profit_factor"] == 1.5

    def test_no_service_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="requires a graph connection"):
            run_preset("promotion_candidates", {}, service=None)

    def test_no_params_valid(self) -> None:
        spec = resolve_preset("promotion_candidates")
        assert validate_params(spec, {}) == []

    def test_unknown_param_rejected(self) -> None:
        spec = resolve_preset("promotion_candidates")
        errors = validate_params(spec, {"min_trades": "30"})
        assert any("unknown param" in e for e in errors)

    def test_empty_result_returned_gracefully(self) -> None:
        class EmptyService(FakeGraphQueryService):
            def get_promotion_candidates_v1(
                self,
                min_sharpe: float = 2.0,
                min_profit_factor: float = 1.3,
            ) -> list[dict[str, Any]]:
                self.calls.append(("get_promotion_candidates_v1", {}))
                return []

        service = EmptyService()
        results = run_preset("promotion_candidates", {}, service=service)
        assert results == []

    def test_output_contains_expected_fields(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("promotion_candidates", {}, service=service)
        row = results[0]
        assert {"run_id", "strategy_id", "sharpe", "tier", "profit_factor",
                "total_trades", "active_window_frequency", "duty_cycle",
                "evidence_score", "ingested_at"}.issubset(row.keys())

    def test_output_includes_tier_column(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("promotion_candidates", {}, service=service)
        assert results[0]["tier"] == "professional"

    def test_output_includes_frequency_and_duty_cycle(self) -> None:
        service = FakeGraphQueryService()
        results = run_preset("promotion_candidates", {}, service=service)
        row = results[0]
        assert row["active_window_frequency"] == 0.12
        assert row["duty_cycle"] == 0.35
