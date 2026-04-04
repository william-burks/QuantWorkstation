"""Shared Graph V1 read projections for Story 1.

This module is the code-defined Query API boundary for Epic 2. Callers bind to
stable function names from `QUERY_VIEW_REGISTRY` instead of embedding ad-hoc
Cypher. All query surfaces read only from canonical Graph V1 labels and edges:
`Strategy`, `Run`, `Config`, `Champion`, `BlobArtifact`, plus `HAS_RUN`,
`USES_CONFIG`, `PRODUCED_CHAMPION`, `PIVOTED_FROM`, and `HAS_BLOB`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from neo4j import GraphDatabase

from .query_models import (
    ChampionDetailsV1,
    ConfigLinkageV1,
    RunHistoryItemV1,
    StrategyLineageV1,
    StrategySummaryV1,
)


GET_STRATEGY_SUMMARY_V1_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})
CALL {
  WITH s
  OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
  RETURN count(r) AS run_count
}
CALL {
  WITH s
  OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
  WITH r
  ORDER BY r.timestamp DESC, r.run_id ASC
  RETURN r.run_id AS latest_run_id, r.timestamp AS latest_run_timestamp
  LIMIT 1
}
CALL {
  WITH s
  OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
  RETURN count(ch) AS champion_count
}
CALL {
  WITH s
  OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
  WITH ch
  ORDER BY ch.freeze_date DESC, ch.champion_id ASC
  RETURN ch.champion_id AS latest_champion_id, ch.freeze_date AS latest_champion_freeze_date
  LIMIT 1
}
RETURN {
  strategy_id: s.strategy_id,
  instrument: s.instrument,
  timeframe: s.timeframe,
  direction: s.direction,
  logic_type: s.logic_type,
  run_count: run_count,
  champion_count: champion_count,
  latest_run_id: latest_run_id,
  latest_run_timestamp: latest_run_timestamp,
  latest_champion_id: latest_champion_id,
  latest_champion_freeze_date: latest_champion_freeze_date
} AS result
""".strip()

GET_RUN_HISTORY_V1_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})-[:HAS_RUN]->(r:Run)
OPTIONAL MATCH (r)-[:USES_CONFIG]->(c:Config)
RETURN {
  strategy_id: s.strategy_id,
  run_id: r.run_id,
  timestamp: r.timestamp,
  sharpe: r.sharpe,
  profit_factor: r.profit_factor,
  win_rate: r.win_rate,
  max_drawdown: r.max_drawdown,
  total_trades: r.total_trades,
  total_r: r.total_r,
  artifact_path: r.artifact_path,
  config_id: c.config_id
} AS result
ORDER BY r.timestamp DESC, r.run_id ASC
""".strip()

GET_CHAMPION_DETAILS_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion {champion_id: $champion_id})
OPTIONAL MATCH (ch)-[:PIVOTED_FROM]->(r:Run)
RETURN {
  champion_id: ch.champion_id,
  strategy_id: s.strategy_id,
  freeze_date: ch.freeze_date,
  oos_status: ch.oos_status,
  fragilities: ch.fragilities,
  artifact_path: ch.artifact_path,
  pivot_from_run_id: r.run_id,
  metrics_summary: ch.metrics_summary
} AS result
LIMIT 1
""".strip()

GET_CONFIG_LINKAGE_V1_CYPHER = """
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run {run_id: $run_id})
OPTIONAL MATCH (r)-[:USES_CONFIG]->(c:Config)
RETURN {
  strategy_id: s.strategy_id,
  run_id: r.run_id,
  config_id: c.config_id,
  params_json: c.params_json,
  risk_params: c.risk_params
} AS result
LIMIT 1
""".strip()

GET_STRATEGY_LINEAGE_V1_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})-[:PRODUCED_CHAMPION]->(ch:Champion)
OPTIONAL MATCH (ch)-[:PIVOTED_FROM]->(r:Run)
OPTIONAL MATCH (r)-[:USES_CONFIG]->(c:Config)
RETURN {
  strategy_id: s.strategy_id,
  champion_id: ch.champion_id,
  freeze_date: ch.freeze_date,
  oos_status: ch.oos_status,
  pivot_from_run_id: r.run_id,
  pivot_run_timestamp: r.timestamp,
  pivot_run_artifact_path: r.artifact_path,
  pivot_config_id: c.config_id
} AS result
ORDER BY ch.freeze_date DESC, ch.champion_id ASC
""".strip()

GET_RECENT_CHAMPIONS_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
OPTIONAL MATCH (ch)-[:PIVOTED_FROM]->(r:Run)
RETURN {
  champion_id: ch.champion_id,
  strategy_id: s.strategy_id,
  freeze_date: ch.freeze_date,
  oos_status: ch.oos_status,
  fragilities: ch.fragilities,
  artifact_path: ch.artifact_path,
  pivot_from_run_id: r.run_id,
  metrics_summary: ch.metrics_summary
} AS result
ORDER BY ch.freeze_date DESC, ch.champion_id ASC
""".strip()


class QuerySession(Protocol):
    """Small protocol for Neo4j read sessions and test doubles."""

    def run(self, query: str, **parameters: Any) -> Iterable[Any]:
        """Execute a read query and return an iterable of records."""


class GraphQueryService:
    """Thin Neo4j-backed wrapper around the Story 1 query functions."""

    def __init__(self, uri: str, username: str, password: str, timeout_seconds: int = 3, database: str = "neo4j"):
        self._database = database
        self._driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=timeout_seconds,
            max_connection_lifetime=300,
        )

    @classmethod
    def from_env(cls, timeout_seconds: int = 3) -> GraphQueryService:
        scheme = os.getenv("QW_GRAPH_SCHEME", "bolt")
        host = os.getenv("QW_GRAPH_HOST", "127.0.0.1")
        port = int(os.getenv("QW_GRAPH_PORT", "7687"))
        user = os.getenv("QW_GRAPH_USER", "neo4j")
        password = os.getenv("QW_GRAPH_PASSWORD", "password")
        database = os.getenv("QW_GRAPH_DATABASE", "neo4j")
        uri = f"{scheme}://{host}:{port}"
        return cls(uri=uri, username=user, password=password, timeout_seconds=timeout_seconds, database=database)

    def close(self) -> None:
        self._driver.close()

    def get_strategy_summary_v1(self, strategy_id: str) -> dict[str, Any] | None:
        with self._driver.session(database=self._database) as session:
            return get_strategy_summary_v1(session, strategy_id)

    def get_run_history_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_run_history_v1(session, strategy_id)

    def get_champion_details_v1(self, champion_id: str) -> dict[str, Any] | None:
        with self._driver.session(database=self._database) as session:
            return get_champion_details_v1(session, champion_id)

    def get_config_linkage_v1(self, run_id: str) -> dict[str, Any] | None:
        with self._driver.session(database=self._database) as session:
            return get_config_linkage_v1(session, run_id)

    def get_strategy_lineage_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_strategy_lineage_v1(session, strategy_id)

    def get_recent_champions_v1(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_recent_champions_v1(session, limit=limit)


def _record_to_mapping(record: Any) -> dict[str, Any]:
    if hasattr(record, "data") and callable(record.data):
        data = record.data()
        if isinstance(data, Mapping):
            return dict(data)
        return dict(data)
    if isinstance(record, Mapping):
        return dict(record)
    return dict(record)


def _normalize_temporal(value: Any) -> Any:
    if value is None:
        return None
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return value


def _normalize_json_like(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                return value
        else:
            return value

    if isinstance(value, Mapping):
        return {key: _normalize_json_like(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_json_like(item) for item in value]
    return _normalize_temporal(value)


def _extract_result_row(record: Any) -> dict[str, Any]:
    row = _record_to_mapping(record)
    result = row.get("result", row)
    if isinstance(result, Mapping):
        return dict(result)
    raise TypeError(f"Query result row must be a mapping, got {type(result)!r}")


def _first_result(session: QuerySession, query: str, **parameters: Any) -> dict[str, Any] | None:
    for record in session.run(query, **parameters):
        return _extract_result_row(record)
    return None


def _all_results(session: QuerySession, query: str, **parameters: Any) -> list[dict[str, Any]]:
    return [_extract_result_row(record) for record in session.run(query, **parameters)]


def _sort_run_history(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with_timestamp = [item for item in items if item["timestamp"] is not None]
    without_timestamp = [item for item in items if item["timestamp"] is None]

    with_timestamp.sort(key=lambda item: item["run_id"])
    with_timestamp.sort(key=lambda item: item["timestamp"], reverse=True)
    without_timestamp.sort(key=lambda item: item["run_id"])
    return with_timestamp + without_timestamp


def _sort_lineage(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with_freeze_date = [item for item in items if item["freeze_date"] is not None]
    without_freeze_date = [item for item in items if item["freeze_date"] is None]

    with_freeze_date.sort(key=lambda item: item["champion_id"])
    with_freeze_date.sort(key=lambda item: item["freeze_date"], reverse=True)
    without_freeze_date.sort(key=lambda item: item["champion_id"])
    return with_freeze_date + without_freeze_date


def get_strategy_summary_v1(session: QuerySession, strategy_id: str) -> dict[str, Any] | None:
    """Return one stable strategy summary projection or `None` when missing."""

    row = _first_result(session, GET_STRATEGY_SUMMARY_V1_CYPHER, strategy_id=strategy_id)
    if row is None:
        return None

    model = StrategySummaryV1(
        strategy_id=str(row["strategy_id"]),
        instrument=str(row["instrument"]),
        timeframe=str(row["timeframe"]),
        direction=str(row["direction"]),
        logic_type=str(row["logic_type"]),
        run_count=int(row.get("run_count") or 0),
        champion_count=int(row.get("champion_count") or 0),
        latest_run_id=row.get("latest_run_id"),
        latest_run_timestamp=_normalize_temporal(row.get("latest_run_timestamp")),
        latest_champion_id=row.get("latest_champion_id"),
        latest_champion_freeze_date=_normalize_temporal(row.get("latest_champion_freeze_date")),
    )
    return model.model_dump(mode="json")


def get_run_history_v1(session: QuerySession, strategy_id: str) -> list[dict[str, Any]]:
    """Return deterministic run-history rows for a strategy."""

    rows = _all_results(session, GET_RUN_HISTORY_V1_CYPHER, strategy_id=strategy_id)
    items = [
        RunHistoryItemV1(
            strategy_id=str(row["strategy_id"]),
            run_id=str(row["run_id"]),
            timestamp=str(_normalize_temporal(row["timestamp"])),
            sharpe=float(row["sharpe"]),
            profit_factor=float(row["profit_factor"]),
            win_rate=float(row["win_rate"]),
            max_drawdown=float(row["max_drawdown"]),
            total_trades=int(row["total_trades"]),
            total_r=None if row.get("total_r") is None else float(row["total_r"]),
            artifact_path=str(row["artifact_path"]),
            config_id=row.get("config_id"),
        ).model_dump(mode="json")
        for row in rows
    ]
    return _sort_run_history(items)


def get_champion_details_v1(session: QuerySession, champion_id: str) -> dict[str, Any] | None:
    """Return one champion detail projection or `None` when missing."""

    row = _first_result(session, GET_CHAMPION_DETAILS_V1_CYPHER, champion_id=champion_id)
    if row is None:
        return None

    model = ChampionDetailsV1(
        champion_id=str(row["champion_id"]),
        strategy_id=str(row["strategy_id"]),
        freeze_date=str(_normalize_temporal(row["freeze_date"])),
        oos_status=str(row["oos_status"]),
        fragilities=list(row.get("fragilities") or []),
        artifact_path=str(row["artifact_path"]),
        pivot_from_run_id=row.get("pivot_from_run_id"),
        metrics_summary=_normalize_json_like(row.get("metrics_summary") or {}),
    )
    return model.model_dump(mode="json")


def get_config_linkage_v1(session: QuerySession, run_id: str) -> dict[str, Any] | None:
    """Return one run-to-config linkage projection or `None` when run is missing."""

    row = _first_result(session, GET_CONFIG_LINKAGE_V1_CYPHER, run_id=run_id)
    if row is None:
        return None

    model = ConfigLinkageV1(
        strategy_id=str(row["strategy_id"]),
        run_id=str(row["run_id"]),
        config_id=row.get("config_id"),
        params_json=None if row.get("params_json") is None else _normalize_json_like(row["params_json"]),
        risk_params=None if row.get("risk_params") is None else _normalize_json_like(row["risk_params"]),
    )
    return model.model_dump(mode="json")


def get_strategy_lineage_v1(session: QuerySession, strategy_id: str) -> list[dict[str, Any]]:
    """Return champion lineage rows for a strategy with explicit optional pivots."""

    rows = _all_results(session, GET_STRATEGY_LINEAGE_V1_CYPHER, strategy_id=strategy_id)
    items = [
        StrategyLineageV1(
            strategy_id=str(row["strategy_id"]),
            champion_id=str(row["champion_id"]),
            freeze_date=str(_normalize_temporal(row["freeze_date"])),
            oos_status=str(row["oos_status"]),
            pivot_from_run_id=row.get("pivot_from_run_id"),
            pivot_run_timestamp=_normalize_temporal(row.get("pivot_run_timestamp")),
            pivot_run_artifact_path=row.get("pivot_run_artifact_path"),
            pivot_config_id=row.get("pivot_config_id"),
        ).model_dump(mode="json")
        for row in rows
    ]
    return _sort_lineage(items)


def get_recent_champions_v1(session: QuerySession, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent champions across all strategies, most recent freeze_date first."""

    rows = _all_results(session, GET_RECENT_CHAMPIONS_V1_CYPHER)
    items = [
        ChampionDetailsV1(
            champion_id=str(row["champion_id"]),
            strategy_id=str(row["strategy_id"]),
            freeze_date=str(_normalize_temporal(row["freeze_date"])),
            oos_status=str(row["oos_status"]),
            fragilities=list(row.get("fragilities") or []),
            artifact_path=str(row["artifact_path"]),
            pivot_from_run_id=row.get("pivot_from_run_id"),
            metrics_summary=_normalize_json_like(row.get("metrics_summary") or {}),
        ).model_dump(mode="json")
        for row in rows
    ]
    return items[:limit]


QUERY_VIEW_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_strategy_summary_v1": get_strategy_summary_v1,
    "get_run_history_v1": get_run_history_v1,
    "get_champion_details_v1": get_champion_details_v1,
    "get_config_linkage_v1": get_config_linkage_v1,
    "get_strategy_lineage_v1": get_strategy_lineage_v1,
    "get_recent_champions_v1": get_recent_champions_v1,
}


def get_query_view(name: str) -> Callable[..., Any]:
    """Resolve a stable Story 1 view function by name."""

    try:
        return QUERY_VIEW_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown query view: {name}") from exc


__all__ = [
    "GET_CHAMPION_DETAILS_V1_CYPHER",
    "GET_CONFIG_LINKAGE_V1_CYPHER",
    "GET_RECENT_CHAMPIONS_V1_CYPHER",
    "GET_RUN_HISTORY_V1_CYPHER",
    "GET_STRATEGY_LINEAGE_V1_CYPHER",
    "GET_STRATEGY_SUMMARY_V1_CYPHER",
    "GraphQueryService",
    "QUERY_VIEW_REGISTRY",
    "get_champion_details_v1",
    "get_config_linkage_v1",
    "get_query_view",
    "get_recent_champions_v1",
    "get_run_history_v1",
    "get_strategy_lineage_v1",
    "get_strategy_summary_v1",
]


