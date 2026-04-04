"""Versioned read DTOs for Graph V1 query projections.

These models are the internal read contract for Epic 2 Story 1. They map only to
canonical Graph V1 labels and edges from `docs/graph_v1_contract.md` and the
Story 0 schema mapping contract:

- `StrategySummaryV1`: one flat strategy summary object
- `RunHistoryItemV1`: one flat run/history row ("ResearchRun" is DTO-doc alias only)
- `ChampionDetailsV1`: one flat champion detail object with parsed metrics
- `ConfigLinkageV1`: one flat run-to-config linkage object
- `StrategyLineageV1`: one flat champion-to-pivot-run lineage row

All outputs are JSON-friendly, deterministic dictionaries (or lists of flat
objects) for CLI preset and MCP consumers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryModelV1(BaseModel):
    """Base class for Story 1 read DTOs."""

    model_config = ConfigDict(extra="ignore")

    version: Literal["v1"] = "v1"


class StrategySummaryV1(QueryModelV1):
    """Strategy-level summary for run/champion counts and most recent activity."""

    strategy_id: str
    instrument: str
    timeframe: str
    direction: str
    logic_type: str
    run_count: int = 0
    champion_count: int = 0
    latest_run_id: str | None = None
    latest_run_timestamp: str | None = None
    latest_champion_id: str | None = None
    latest_champion_freeze_date: str | None = None


class RunHistoryItemV1(QueryModelV1):
    """One run-history row linked back to its canonical Strategy and Config."""

    strategy_id: str
    run_id: str
    timestamp: str
    sharpe: float
    profit_factor: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    total_r: float | None = None
    artifact_path: str
    config_id: str | None = None


class ChampionDetailsV1(QueryModelV1):
    """Champion detail surface with explicit optional pivot linkage."""

    champion_id: str
    strategy_id: str
    freeze_date: str
    oos_status: str
    fragilities: list[str] = Field(default_factory=list)
    artifact_path: str
    pivot_from_run_id: str | None = None
    metrics_summary: dict[str, Any] = Field(default_factory=dict)


class ConfigLinkageV1(QueryModelV1):
    """Run-to-config linkage surface with parsed config payloads."""

    strategy_id: str
    run_id: str
    config_id: str | None = None
    params_json: dict[str, Any] | None = None
    risk_params: dict[str, Any] | None = None


class StrategyLineageV1(QueryModelV1):
    """Champion lineage row keyed by strategy and optional explicit pivot run."""

    strategy_id: str
    champion_id: str
    freeze_date: str
    oos_status: str
    pivot_from_run_id: str | None = None
    pivot_run_timestamp: str | None = None
    pivot_run_artifact_path: str | None = None
    pivot_config_id: str | None = None


__all__ = [
    "ChampionDetailsV1",
    "ConfigLinkageV1",
    "QueryModelV1",
    "RunHistoryItemV1",
    "StrategyLineageV1",
    "StrategySummaryV1",
]

