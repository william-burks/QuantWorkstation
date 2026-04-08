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
    CrossArtifactRowV1,
    RunHistoryItemV1,
    RunStatsSummaryV1,
    StrategyLineageV1,
    StrategySummaryV1,
)


GET_STRATEGY_SUMMARY_V1_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})
CALL (s) {
  OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
  RETURN count(r) AS run_count
}
CALL (s) {
  OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
  WITH r
  ORDER BY r.timestamp DESC, r.run_id ASC
  RETURN r.run_id AS latest_run_id, r.timestamp AS latest_run_timestamp
  LIMIT 1
}
CALL (s) {
  OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
  RETURN count(ch) AS champion_count
}
CALL (s) {
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
  family_id: s.family_id,
  status: s.status,
  abort_reason: s.abort_reason,
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
WHERE s.status <> 'ABORTED'
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
  config_id: c.config_id,
  curator_note: r.curator_note
} AS result
ORDER BY r.timestamp ASC, r.run_id ASC
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
WHERE s.status <> 'ABORTED'
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
WHERE s.status <> 'ABORTED'
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

GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)-[:PIVOTED_FROM]->(r:Run {run_id: $run_id})
WHERE s.status <> 'ABORTED'
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

GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER = """
MATCH (anchor:Strategy {strategy_id: $strategy_id})
MATCH (related:Strategy)
WHERE (
  (
    anchor.family_id IS NOT NULL
    AND related.family_id = anchor.family_id
    AND related.strategy_id <> anchor.strategy_id
  ) OR (
    anchor.family_id IS NULL
    AND related.logic_type = anchor.logic_type
    AND related.direction = anchor.direction
    AND related.strategy_id <> anchor.strategy_id
  )
)
AND anchor.status <> 'ABORTED'
AND related.status <> 'ABORTED'
CALL (related) {
  OPTIONAL MATCH (related)-[:HAS_RUN]->(r:Run)
  RETURN count(r) AS run_count
}
CALL (related) {
  OPTIONAL MATCH (related)-[:PRODUCED_CHAMPION]->(ch:Champion)
  RETURN count(ch) AS champion_count
}
CALL (related) {
  OPTIONAL MATCH (related)-[:PRODUCED_CHAMPION]->(ch:Champion)
  WITH ch
  ORDER BY ch.freeze_date DESC, ch.champion_id ASC
  RETURN ch.champion_id AS latest_champion_id, ch.freeze_date AS latest_champion_freeze_date
  LIMIT 1
}
RETURN {
  anchor_strategy_id: anchor.strategy_id,
  related_strategy_id: related.strategy_id,
  instrument: related.instrument,
  timeframe: related.timeframe,
  direction: related.direction,
  logic_type: related.logic_type,
  family_id: related.family_id,
  run_count: run_count,
  champion_count: champion_count,
  latest_champion_id: latest_champion_id,
  latest_champion_freeze_date: latest_champion_freeze_date
} AS result
ORDER BY related.instrument ASC, related.timeframe ASC
""".strip()

GET_FAMILY_CLUSTER_V1_CYPHER = """
MATCH (s:Strategy {family_id: $family_id})
WHERE s.status <> 'ABORTED'
CALL (s) {
  OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
  RETURN count(r) AS run_count
}
CALL (s) {
  OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
  RETURN count(ch) AS champion_count
}
CALL (s) {
  OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
  WITH ch
  ORDER BY ch.freeze_date DESC, ch.champion_id ASC
  RETURN ch.champion_id AS latest_champion_id, ch.freeze_date AS latest_champion_freeze_date
  LIMIT 1
}
RETURN {
  anchor_strategy_id: $family_id,
  related_strategy_id: s.strategy_id,
  instrument: s.instrument,
  timeframe: s.timeframe,
  direction: s.direction,
  logic_type: s.logic_type,
  family_id: s.family_id,
  run_count: run_count,
  champion_count: champion_count,
  latest_champion_id: latest_champion_id,
  latest_champion_freeze_date: latest_champion_freeze_date
} AS result
ORDER BY s.instrument ASC, s.timeframe ASC
""".strip()


GET_PORTFOLIO_ALPHA_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE ch.tier IN ['professional', 'institutional']
  AND s.status <> 'ABORTED'
WITH count(ch) AS champion_count,
     sum(ch.metrics_return) AS total_return,
     avg(ch.metrics_sharpe) AS avg_sharpe,
     collect(ch.strategy_id) AS strategies
RETURN {
  champion_count: champion_count,
  total_return: total_return,
  avg_sharpe: avg_sharpe,
  strategies: strategies
} AS result
""".strip()

GET_FRAGILITY_REPORT_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE any(f IN ch.fragilities WHERE toLower(f) CONTAINS 'regime')
RETURN {
  strategy_id: ch.strategy_id,
  champion_id: ch.champion_id,
  tier: ch.tier,
  oos_status: ch.oos_status,
  fragilities: ch.fragilities
} AS result
ORDER BY ch.strategy_id ASC
""".strip()

GET_LIST_OOS_PENDING_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE ch.oos_status = 'oos_pending'
  AND s.status <> 'ABORTED'
RETURN {
  champion_id: ch.champion_id,
  strategy_id: ch.strategy_id,
  freeze_date: toString(ch.freeze_date),
  metrics_sharpe: ch.metrics_sharpe,
  metrics_total_trades: ch.metrics_total_trades,
  days_pending: duration.between(ch.freeze_date, date()).days
} AS result
ORDER BY ch.freeze_date ASC
""".strip()

GET_LIST_ABORTED_V1_CYPHER = """
MATCH (s:Strategy)
WHERE s.status = 'ABORTED'
RETURN {
  strategy_id: s.strategy_id,
  instrument: s.instrument,
  direction: s.direction,
  logic_type: s.logic_type,
  abort_reason: s.abort_reason,
  aborted_at: toString(s.aborted_at)
} AS result
ORDER BY s.aborted_at DESC
""".strip()

GET_PROMOTION_CANDIDATES_V1_CYPHER = """
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)
WHERE s.status <> 'ABORTED'
  AND r.sharpe >= $min_sharpe
  AND r.profit_factor >= $min_profit_factor
  AND r.total_trades >= 30
  AND r.active_window_frequency >= 0.06
  AND NOT EXISTS { MATCH (ch:Champion)-[:PIVOTED_FROM]->(r) }
WITH r, s, (r.sharpe * sqrt(toFloat(r.total_trades))) AS evidence_score
ORDER BY evidence_score DESC
RETURN {
  run_id: r.run_id,
  strategy_id: s.strategy_id,
  sharpe: r.sharpe,
  tier: r.tier,
  profit_factor: r.profit_factor,
  total_trades: r.total_trades,
  active_window_frequency: r.active_window_frequency,
  duty_cycle: r.duty_cycle,
  evidence_score: evidence_score,
  ingested_at: toString(r.ingested_at)
} AS result
""".strip()

GET_STALENESS_REPORT_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE s.status <> 'ABORTED'
WITH ch, duration.between(ch.freeze_date, date()).days AS days_old
WHERE days_old > 30
RETURN {
  strategy_id: ch.strategy_id,
  champion_id: ch.champion_id,
  days_old: days_old,
  oos_status: ch.oos_status,
  tier: ch.tier
} AS result
ORDER BY days_old DESC
""".strip()

GET_INSTRUMENT_CONCENTRATION_V1_CYPHER = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE s.status <> 'ABORTED'
WITH s.instrument AS instrument,
     count(ch) AS champion_count,
     sum(ch.metrics_return) AS total_return
RETURN {
  instrument: instrument,
  champion_count: champion_count,
  total_return: total_return
} AS result
ORDER BY champion_count DESC
""".strip()

GET_RESEARCH_TARGETS_V1_CYPHER = """
MATCH (rt:ResearchTarget {target_id: "singleton"})
RETURN {
  sharpe_professional: rt.sharpe_professional,
  sharpe_institutional: rt.sharpe_institutional,
  max_holding_hours: rt.max_holding_hours,
  min_trades: rt.min_trades,
  min_active_window_frequency: rt.min_active_window_frequency,
  profit_factor_min: rt.profit_factor_min,
  calmar_min: rt.calmar_min,
  max_drawdown_floor: rt.max_drawdown_floor,
  correlation_gate: rt.correlation_gate,
  updated_at: toString(rt.updated_at)
} AS result
""".strip()


GET_RUN_STATS_SUMMARY_V1_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})-[:HAS_RUN_SUMMARY]->(rss:RunStatsSummary)
RETURN {
  summary_id: rss.summary_id,
  strategy_id: rss.strategy_id,
  artifact_path: rss.artifact_path,
  total_run_count: rss.total_run_count,
  selected_run_count: rss.selected_run_count,
  rolled_up_run_count: rss.rolled_up_run_count,
  sharpe_mean: rss.sharpe_mean,
  sharpe_max: rss.sharpe_max,
  sharpe_min: rss.sharpe_min,
  max_drawdown_worst: rss.max_drawdown_worst,
  ingested_at: rss.ingested_at
} AS result
ORDER BY rss.ingested_at DESC
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

    def get_downstream_champions_v1(self, run_id: str) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_downstream_champions_v1(session, run_id)

    def get_cross_artifact_correlation_v1(
        self,
        strategy_id: str | None = None,
        family_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_cross_artifact_correlation_v1(session, strategy_id=strategy_id, family_id=family_id)

    def get_run_stats_summary_v1(self, strategy_id: str) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_run_stats_summary_v1(session, strategy_id)

    def get_staleness_report_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_staleness_report_v1(session)

    def get_instrument_concentration_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_instrument_concentration_v1(session)

    def get_portfolio_alpha_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_portfolio_alpha_v1(session)

    def get_fragility_report_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_fragility_report_v1(session)

    def get_list_oos_pending_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_list_oos_pending_v1(session)

    def get_list_aborted_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_list_aborted_v1(session)

    def get_promotion_candidates_v1(
        self,
        min_sharpe: float = 2.0,
        min_profit_factor: float = 1.3,
    ) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_promotion_candidates_v1(
                session,
                min_sharpe=min_sharpe,
                min_profit_factor=min_profit_factor,
            )

    def get_research_targets_v1(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return get_research_targets_v1(session)


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
    with_timestamp.sort(key=lambda item: item["timestamp"])
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
        family_id=row.get("family_id"),
        status=row.get("status"),
        abort_reason=row.get("abort_reason"),
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
            curator_note=row.get("curator_note"),
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


def get_downstream_champions_v1(session: QuerySession, run_id: str) -> list[dict[str, Any]]:
    """Return champions that pivoted from *run_id* via an explicit PIVOTED_FROM edge.

    Traversal depth: one hop (``Champion-[:PIVOTED_FROM]->Run``).
    Returns an empty list when no explicit pivot edges exist for *run_id*.
    Only PIVOTED_FROM edges written at ingest time are traversed; no inferred pivots.
    """

    rows = _all_results(session, GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER, run_id=run_id)
    return [
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


def get_cross_artifact_correlation_v1(
    session: QuerySession,
    strategy_id: str | None = None,
    family_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return correlated strategies by anchor strategy or direct family_id.

    Traversal depth: one hop from the anchor ``Strategy`` node to related ``Strategy``
    nodes matched by shared family or canonical properties. No file-system reads; no
    new persisted labels.

    Mode A (strategy_id provided): anchors on the given strategy and returns all other
    strategies in its family. Falls back to ``logic_type + direction`` when
    ``family_id IS NULL`` on the anchor.

    Mode B (family_id provided): returns ALL strategies with ``strategy.family_id =
    family_id`` — no anchor required. The ``anchor_strategy_id`` field is set to the
    ``family_id`` string to make the query axis explicit to callers.

    When both are provided, Mode B (family_id) takes precedence.

    Raises:
        ValueError: When neither strategy_id nor family_id is provided.
    """
    if family_id is not None:
        rows = _all_results(session, GET_FAMILY_CLUSTER_V1_CYPHER, family_id=family_id)
    elif strategy_id is not None:
        rows = _all_results(session, GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER, strategy_id=strategy_id)
    else:
        raise ValueError("get_cross_artifact_correlation_v1 requires strategy_id or family_id")

    return [
        CrossArtifactRowV1(
            anchor_strategy_id=str(row["anchor_strategy_id"]),
            related_strategy_id=str(row["related_strategy_id"]),
            instrument=str(row["instrument"]),
            timeframe=str(row["timeframe"]),
            direction=str(row["direction"]),
            logic_type=str(row["logic_type"]),
            family_id=row.get("family_id"),
            run_count=int(row.get("run_count") or 0),
            champion_count=int(row.get("champion_count") or 0),
            latest_champion_id=row.get("latest_champion_id"),
            latest_champion_freeze_date=_normalize_temporal(row.get("latest_champion_freeze_date")),
        ).model_dump(mode="json")
        for row in rows
    ]


def get_run_stats_summary_v1(session: QuerySession, strategy_id: str) -> list[dict[str, Any]]:
    """Return ``RunStatsSummary`` nodes for *strategy_id*, most recent first.

    Returns an empty list when no summary nodes exist for the strategy.
    Summary nodes are created by the significance gate during ``grid_csv`` ingest.
    """

    rows = _all_results(session, GET_RUN_STATS_SUMMARY_V1_CYPHER, strategy_id=strategy_id)
    return [
        RunStatsSummaryV1(
            summary_id=str(row["summary_id"]),
            strategy_id=str(row["strategy_id"]),
            artifact_path=str(row["artifact_path"]),
            total_run_count=int(row["total_run_count"]),
            selected_run_count=int(row["selected_run_count"]),
            rolled_up_run_count=int(row["rolled_up_run_count"]),
            sharpe_mean=float(row["sharpe_mean"]),
            sharpe_max=float(row["sharpe_max"]),
            sharpe_min=float(row["sharpe_min"]),
            max_drawdown_worst=float(row["max_drawdown_worst"]),
            ingested_at=str(_normalize_temporal(row["ingested_at"])),
        ).model_dump(mode="json")
        for row in rows
    ]


def get_staleness_report_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return Champions frozen more than 30 days ago, ordered by age descending."""
    return _all_results(session, GET_STALENESS_REPORT_V1_CYPHER)


def get_instrument_concentration_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return champion count and total return aggregated by instrument."""
    return _all_results(session, GET_INSTRUMENT_CONCENTRATION_V1_CYPHER)


def get_portfolio_alpha_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return aggregate return and Sharpe across professional/institutional Champions."""
    return _all_results(session, GET_PORTFOLIO_ALPHA_V1_CYPHER)


def get_fragility_report_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return Champions whose fragilities mention regime sensitivity."""
    return _all_results(session, GET_FRAGILITY_REPORT_V1_CYPHER)


def get_list_oos_pending_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return Champions with oos_status = oos_pending, oldest freeze_date first."""
    return _all_results(session, GET_LIST_OOS_PENDING_V1_CYPHER)


def get_list_aborted_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return all Strategies with status = ABORTED, most recently aborted first."""
    return _all_results(session, GET_LIST_ABORTED_V1_CYPHER)


def get_promotion_candidates_v1(
    session: QuerySession,
    min_sharpe: float = 2.0,
    min_profit_factor: float = 1.3,
) -> list[dict[str, Any]]:
    """Return Run nodes that pass the dual-hurdle gate and have no linked Champion.

    Hard gates (not overridable): total_trades >= 30, active_window_frequency >= 0.06.
    Overridable via params: min_sharpe (default 2.0), min_profit_factor (default 1.3).
    Ordered by evidence_score (sharpe * sqrt(total_trades)) descending.
    """
    return _all_results(
        session,
        GET_PROMOTION_CANDIDATES_V1_CYPHER,
        min_sharpe=min_sharpe,
        min_profit_factor=min_profit_factor,
    )


def get_research_targets_v1(session: QuerySession) -> list[dict[str, Any]]:
    """Return all properties of the singleton ResearchTarget node.

    Returns a list with one dict when the node exists, empty list when not yet seeded.
    Use ``qw seed --targets`` to create the node.
    """
    return _all_results(session, GET_RESEARCH_TARGETS_V1_CYPHER)


QUERY_VIEW_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_strategy_summary_v1": get_strategy_summary_v1,
    "get_run_history_v1": get_run_history_v1,
    "get_champion_details_v1": get_champion_details_v1,
    "get_config_linkage_v1": get_config_linkage_v1,
    "get_strategy_lineage_v1": get_strategy_lineage_v1,
    "get_recent_champions_v1": get_recent_champions_v1,
    "get_downstream_champions_v1": get_downstream_champions_v1,
    "get_cross_artifact_correlation_v1": get_cross_artifact_correlation_v1,
    "get_run_stats_summary_v1": get_run_stats_summary_v1,
    "get_portfolio_alpha_v1": get_portfolio_alpha_v1,
    "get_fragility_report_v1": get_fragility_report_v1,
    "get_staleness_report_v1": get_staleness_report_v1,
    "get_instrument_concentration_v1": get_instrument_concentration_v1,
    "get_list_oos_pending_v1": get_list_oos_pending_v1,
    "get_list_aborted_v1": get_list_aborted_v1,
    "get_promotion_candidates_v1": get_promotion_candidates_v1,
    "get_research_targets_v1": get_research_targets_v1,
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
    "GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER",
    "GET_DOWNSTREAM_CHAMPIONS_V1_CYPHER",
    "GET_FAMILY_CLUSTER_V1_CYPHER",
    "GET_FRAGILITY_REPORT_V1_CYPHER",
    "GET_INSTRUMENT_CONCENTRATION_V1_CYPHER",
    "GET_LIST_ABORTED_V1_CYPHER",
    "GET_LIST_OOS_PENDING_V1_CYPHER",
    "GET_PORTFOLIO_ALPHA_V1_CYPHER",
    "GET_PROMOTION_CANDIDATES_V1_CYPHER",
    "GET_RESEARCH_TARGETS_V1_CYPHER",
    "GET_STALENESS_REPORT_V1_CYPHER",
    "GET_RECENT_CHAMPIONS_V1_CYPHER",
    "GET_RUN_HISTORY_V1_CYPHER",
    "GET_RUN_STATS_SUMMARY_V1_CYPHER",
    "GET_STRATEGY_LINEAGE_V1_CYPHER",
    "GET_STRATEGY_SUMMARY_V1_CYPHER",
    "GraphQueryService",
    "QUERY_VIEW_REGISTRY",
    "get_champion_details_v1",
    "get_config_linkage_v1",
    "get_cross_artifact_correlation_v1",
    "get_downstream_champions_v1",
    "get_fragility_report_v1",
    "get_instrument_concentration_v1",
    "get_list_aborted_v1",
    "get_list_oos_pending_v1",
    "get_portfolio_alpha_v1",
    "get_promotion_candidates_v1",
    "get_research_targets_v1",
    "get_staleness_report_v1",
    "get_query_view",
    "get_recent_champions_v1",
    "get_run_history_v1",
    "get_run_stats_summary_v1",
    "get_strategy_lineage_v1",
    "get_strategy_summary_v1",
]


