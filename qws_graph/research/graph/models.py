"""Pydantic models for V1 graph ingestion.

Reference: docs/graph_v1_contract.md - V1 Schema Definitions (Pydantic-level)
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Provenance(BaseModel):
    """Provenance metadata attached to every ingested node."""

    model_config = ConfigDict(extra="ignore")

    artifact_path: str
    artifact_hash: str
    artifact_mtime_iso: str
    ingested_at: datetime
    parser_version: str = "v1"


class Strategy(BaseModel):
    """Strategy node: identifies an instrument/timeframe/direction/logic combination."""

    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    instrument: str
    timeframe: str
    direction: Literal["long", "short", "bear", "bull"]
    logic_type: str
    family_id: str | None = None


class Config(BaseModel):
    """Config node: parameter set for a run."""

    model_config = ConfigDict(extra="ignore")

    config_id: str
    params_json: dict[str, Any]
    risk_params: dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    """Run node: a single backtest result."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    strategy_id: str
    timestamp: datetime
    sharpe: float
    profit_factor: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    total_r: float | None = None
    calmar: float | None = None
    metrics_return: float | None = None  # CSV column "return" (reserved word)
    tier: str | None = None
    artifact_path: str
    curator_note: str | None = None
    provenance: Provenance

    @field_validator("win_rate")
    @classmethod
    def win_rate_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("win_rate must be in [0,1]")
        return v


class Champion(BaseModel):
    """Champion node: a promoted strategy configuration."""

    model_config = ConfigDict(extra="ignore")

    champion_id: str
    strategy_id: str
    freeze_date: date
    metrics_summary: dict[str, float | int | str]
    oos_status: str
    fragilities: list[str]
    artifact_path: str
    pivot_from_run_id: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_required_content(self) -> Champion:
        if not self.metrics_summary:
            raise ValueError("champion metrics_summary must not be empty")
        if not self.fragilities:
            raise ValueError("champion fragilities must contain at least one entry")
        return self


class RunStatsSummary(BaseModel):
    """Aggregate stats for grid-sweep runs that did not pass the significance gate.

    One node is persisted per (strategy_id, artifact_path, artifact_mtime) triple,
    merged idempotently via ``HAS_RUN_SUMMARY`` from the owning ``Strategy`` node.
    Provides a bounded neighbourhood summary instead of raw run enumeration.
    """

    model_config = ConfigDict(extra="ignore")

    summary_id: str
    strategy_id: str
    artifact_path: str
    total_run_count: int
    selected_run_count: int
    rolled_up_run_count: int
    sharpe_mean: float
    sharpe_max: float
    sharpe_min: float
    max_drawdown_worst: float
    ingested_at: datetime


class BlobArtifact(BaseModel):
    """BlobArtifact node: raw unstructured artifact (e.g., tracker markdown)."""

    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    artifact_path: str
    artifact_kind: Literal["tracker_md"]
    raw_text_sha256: str
    provenance: Provenance


class ResearchArtifact(BaseModel):
    """Root artifact payload: union of CSV and Markdown ingests."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["baseline_csv", "grid_csv", "champion_md", "tracker_md"]
    strategy: Strategy
    runs: list[Run] = Field(default_factory=list)
    configs: list[Config] = Field(default_factory=list)
    champion: Champion | None = None
    blob: BlobArtifact | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ResearchArtifact:
        """Ensure payload shape matches kind."""
        if self.kind in {"baseline_csv", "grid_csv"} and not self.runs:
            raise ValueError("CSV artifacts require at least one run")
        if self.kind in {"baseline_csv", "grid_csv"} and not self.configs:
            raise ValueError("CSV artifacts require at least one config")
        if self.kind in {"baseline_csv", "grid_csv"} and len(self.runs) != len(self.configs):
            raise ValueError("CSV artifacts require one config per run")
        if self.kind == "champion_md" and self.champion is None:
            raise ValueError("champion_md requires champion payload")
        if self.kind == "tracker_md" and self.blob is None:
            raise ValueError("tracker_md requires blob payload")
        return self

