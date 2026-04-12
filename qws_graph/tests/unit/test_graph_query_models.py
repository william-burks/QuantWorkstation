"""Unit tests for Story 1 graph read DTOs and projection functions."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

query_models_module = import_module("research.graph.query_models")
query_module = import_module("research.graph.query")

ChampionDetailsV1 = query_models_module.ChampionDetailsV1
ConfigLinkageV1 = query_models_module.ConfigLinkageV1
RunHistoryItemV1 = query_models_module.RunHistoryItemV1
StrategyLineageV1 = query_models_module.StrategyLineageV1
StrategySummaryV1 = query_models_module.StrategySummaryV1

GET_CHAMPION_DETAILS_V1_CYPHER = query_module.GET_CHAMPION_DETAILS_V1_CYPHER
GET_CONFIG_LINKAGE_V1_CYPHER = query_module.GET_CONFIG_LINKAGE_V1_CYPHER
GET_RUN_HISTORY_V1_CYPHER = query_module.GET_RUN_HISTORY_V1_CYPHER
GET_STRATEGY_LINEAGE_V1_CYPHER = query_module.GET_STRATEGY_LINEAGE_V1_CYPHER
GET_STRATEGY_SUMMARY_V1_CYPHER = query_module.GET_STRATEGY_SUMMARY_V1_CYPHER
get_champion_details_v1 = query_module.get_champion_details_v1
get_config_linkage_v1 = query_module.get_config_linkage_v1
get_query_view = query_module.get_query_view
get_run_history_v1 = query_module.get_run_history_v1
get_strategy_lineage_v1 = query_module.get_strategy_lineage_v1
get_strategy_summary_v1 = query_module.get_strategy_summary_v1


class FakeRecord:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def data(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self, responses: dict[str, list[dict[str, object]]]):
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, query: str, **parameters: object):
        self.calls.append((query, parameters))
        return [FakeRecord(row) for row in self._responses.get(query, [])]


class TestQueryModels:
    def test_strategy_summary_model_has_stable_json_keys(self) -> None:
        model = StrategySummaryV1(
            strategy_id="es-1h-bear-sweep",
            instrument="ES",
            timeframe="1H",
            direction="bear",
            logic_type="sweep",
            run_count=3,
            champion_count=1,
            latest_run_id="run-003",
            latest_run_timestamp="2026-04-02T12:30:00+00:00",
            latest_champion_id="champ-001",
            latest_champion_freeze_date="2026-04-02",
        )

        assert model.model_dump(mode="json") == {
            "version": "v1",
            "strategy_id": "es-1h-bear-sweep",
            "instrument": "ES",
            "timeframe": "1H",
            "direction": "bear",
            "logic_type": "sweep",
            "family_id": None,
            "status": None,
            "abort_reason": None,
            "run_count": 3,
            "champion_count": 1,
            "latest_run_id": "run-003",
            "latest_run_timestamp": "2026-04-02T12:30:00+00:00",
            "latest_champion_id": "champ-001",
            "latest_champion_freeze_date": "2026-04-02",
        }

    def test_other_models_are_json_friendly(self) -> None:
        run = RunHistoryItemV1(
            strategy_id="es-1h-bear-sweep",
            run_id="run-001",
            timestamp="2026-04-02T12:00:00+00:00",
            sharpe=1.25,
            profit_factor=1.1,
            win_rate=0.41,
            max_drawdown=-7.5,
            total_trades=42,
            total_r=8.4,
            artifact_path="results/es.csv",
            config_id="cfg-001",
        )
        champion = ChampionDetailsV1(
            champion_id="champ-001",
            strategy_id="es-1h-bear-sweep",
            freeze_date="2026-04-02",
            oos_status="oos_pending",
            fragilities=["session-dependent edge"],
            artifact_path="research/results/champions/es.md",
            pivot_from_run_id=None,
            metrics_summary={"sample_size": 42, "sharpe": 1.25},
        )
        linkage = ConfigLinkageV1(
            strategy_id="es-1h-bear-sweep",
            run_id="run-001",
            config_id="cfg-001",
            params_json={"sessions": ["NY_PRE"]},
            risk_params={"atr_mult_stop": 0.5},
        )
        lineage = StrategyLineageV1(
            strategy_id="es-1h-bear-sweep",
            champion_id="champ-001",
            freeze_date="2026-04-02",
            oos_status="oos_pending",
            pivot_from_run_id="run-001",
            pivot_run_timestamp="2026-04-01T12:00:00+00:00",
            pivot_run_artifact_path="results/es.csv",
            pivot_config_id="cfg-001",
        )

        assert run.model_dump(mode="json")["version"] == "v1"
        assert champion.model_dump(mode="json")["metrics_summary"]["sample_size"] == 42
        assert linkage.model_dump(mode="json")["risk_params"]["atr_mult_stop"] == 0.5
        assert lineage.model_dump(mode="json")["pivot_from_run_id"] == "run-001"


class TestQueryFunctions:
    def test_strategy_summary_projection_returns_deterministic_json(self) -> None:
        session = FakeSession(
            {
                GET_STRATEGY_SUMMARY_V1_CYPHER: [
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "instrument": "ES",
                            "timeframe": "1H",
                            "direction": "bear",
                            "logic_type": "sweep",
                            "run_count": 3,
                            "champion_count": 1,
                            "latest_run_id": "run-003",
                            "latest_run_timestamp": datetime(2026, 4, 2, 12, 30, tzinfo=UTC),
                            "latest_champion_id": "champ-001",
                            "latest_champion_freeze_date": date(2026, 4, 2),
                        }
                    }
                ]
            }
        )

        result = get_strategy_summary_v1(session, "es-1h-bear-sweep")

        assert session.calls[0] == (
            GET_STRATEGY_SUMMARY_V1_CYPHER, {"strategy_id": "es-1h-bear-sweep"}
        )
        assert json.dumps(result, sort_keys=True, indent=2) == """{
  \"abort_reason\": null,
  \"champion_count\": 1,
  \"direction\": \"bear\",
  \"family_id\": null,
  \"instrument\": \"ES\",
  \"latest_champion_freeze_date\": \"2026-04-02\",
  \"latest_champion_id\": \"champ-001\",
  \"latest_run_id\": \"run-003\",
  \"latest_run_timestamp\": \"2026-04-02T12:30:00+00:00\",
  \"logic_type\": \"sweep\",
  \"run_count\": 3,
  \"status\": null,
  \"strategy_id\": \"es-1h-bear-sweep\",
  \"timeframe\": \"1H\",
  \"version\": \"v1\"
}"""

    def test_strategy_summary_returns_none_when_strategy_missing(self) -> None:
        session = FakeSession({GET_STRATEGY_SUMMARY_V1_CYPHER: []})
        assert get_strategy_summary_v1(session, "missing") is None

    def test_run_history_projection_sorts_multi_edge_rows(self) -> None:
        session = FakeSession(
            {
                GET_RUN_HISTORY_V1_CYPHER: [
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "run_id": "run-002",
                            "timestamp": datetime(2026, 4, 1, 12, 30, tzinfo=UTC),
                            "sharpe": 1.2,
                            "profit_factor": 1.1,
                            "win_rate": 0.42,
                            "max_drawdown": -7.1,
                            "total_trades": 52,
                            "total_r": 9.5,
                            "artifact_path": "results/es_grid.csv",
                            "config_id": None,
                        }
                    },
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "run_id": "run-003",
                            "timestamp": datetime(2026, 4, 2, 12, 30, tzinfo=UTC),
                            "sharpe": 1.3,
                            "profit_factor": 1.2,
                            "win_rate": 0.43,
                            "max_drawdown": -6.9,
                            "total_trades": 60,
                            "total_r": 10.1,
                            "artifact_path": "results/es_grid.csv",
                            "config_id": "cfg-003",
                        }
                    },
                ]
            }
        )

        result = get_run_history_v1(session, "es-1h-bear-sweep")

        assert [item["run_id"] for item in result] == ["run-002", "run-003"]
        assert result[0]["config_id"] is None  # run-002 (earlier) has no config_id

    def test_champion_details_projection_parses_json_and_handles_missing_pivot(self) -> None:
        session = FakeSession(
            {
                GET_CHAMPION_DETAILS_V1_CYPHER: [
                    {
                        "result": {
                            "champion_id": "champ-001",
                            "strategy_id": "es-1h-bear-sweep",
                            "freeze_date": date(2026, 4, 2),
                            "oos_status": "oos_pending",
                            "fragilities": ["session-dependent edge", "slippage sensitivity"],
                            "artifact_path": "research/results/champions/es.md",
                            "pivot_from_run_id": None,
                            "metrics_summary": '{"sharpe":1.25,"sample_size":42}',
                        }
                    }
                ]
            }
        )

        result = get_champion_details_v1(session, "champ-001")

        assert result == {
            "version": "v1",
            "champion_id": "champ-001",
            "strategy_id": "es-1h-bear-sweep",
            "freeze_date": "2026-04-02",
            "oos_status": "oos_pending",
            "fragilities": ["session-dependent edge", "slippage sensitivity"],
            "artifact_path": "research/results/champions/es.md",
            "pivot_from_run_id": None,
            "metrics_summary": {"sample_size": 42, "sharpe": 1.25},
            "promotion_rationale": "",
        }

    def test_config_linkage_projection_returns_empty_optionals_for_missing_edge(self) -> None:
        session = FakeSession(
            {
                GET_CONFIG_LINKAGE_V1_CYPHER: [
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "run_id": "run-002",
                            "config_id": None,
                            "params_json": None,
                            "risk_params": None,
                        }
                    }
                ]
            }
        )

        result = get_config_linkage_v1(session, "run-002")

        assert result == {
            "version": "v1",
            "strategy_id": "es-1h-bear-sweep",
            "run_id": "run-002",
            "config_id": None,
            "params_json": None,
            "risk_params": None,
        }

    def test_strategy_lineage_projection_covers_multi_edge_and_no_edge_cases(self) -> None:
        session = FakeSession(
            {
                GET_STRATEGY_LINEAGE_V1_CYPHER: [
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "champion_id": "champ-older",
                            "freeze_date": date(2026, 4, 1),
                            "oos_status": "oos_pending",
                            "pivot_from_run_id": None,
                            "pivot_run_timestamp": None,
                            "pivot_run_artifact_path": None,
                            "pivot_config_id": None,
                        }
                    },
                    {
                        "result": {
                            "strategy_id": "es-1h-bear-sweep",
                            "champion_id": "champ-newer",
                            "freeze_date": date(2026, 4, 2),
                            "oos_status": "live_paper",
                            "pivot_from_run_id": "run-003",
                            "pivot_run_timestamp": datetime(2026, 4, 2, 12, 30, tzinfo=UTC),
                            "pivot_run_artifact_path": "results/es_grid.csv",
                            "pivot_config_id": "cfg-003",
                        }
                    },
                ]
            }
        )

        result = get_strategy_lineage_v1(session, "es-1h-bear-sweep")

        assert [item["champion_id"] for item in result] == ["champ-newer", "champ-older"]
        assert result[0]["pivot_from_run_id"] == "run-003"
        assert result[1]["pivot_from_run_id"] is None

        empty_session = FakeSession({GET_STRATEGY_LINEAGE_V1_CYPHER: []})
        assert get_strategy_lineage_v1(empty_session, "missing") == []

    def test_query_view_registry_exposes_stable_function_names(self) -> None:
        assert get_query_view("get_strategy_summary_v1") is get_strategy_summary_v1
        with pytest.raises(KeyError, match="Unknown query view"):
            get_query_view("missing_view")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

