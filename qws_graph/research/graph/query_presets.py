"""Query preset catalog for the `qw query` CLI surface (Story 2).

Presets are stable named routing entries that delegate to view functions from
``research.graph.query`` (Story 1) for graph-backed queries, and to filesystem
reads for the ``pending_offline`` preset.

Routing rule: no Cypher lives here. All graph queries go through
``research.graph.query`` view functions referenced by stable function name.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .query import (
    get_cross_artifact_correlation_v1,
    get_downstream_champions_v1,
    get_fragility_report_v1,
    get_instrument_concentration_v1,
    get_list_aborted_v1,
    get_list_oos_pending_v1,
    get_portfolio_alpha_v1,
    get_promotion_candidates_v1,
    get_recent_champions_v1,
    get_regime_performance_v1,
    get_research_targets_v1,
    get_run_history_v1,
    get_runs_by_regime_v1,
    get_staleness_report_v1,
    get_strategy_lineage_v1,
)

if TYPE_CHECKING:
    from .query import GraphQueryService


@dataclass(frozen=True)
class PresetParam:
    name: str
    required: bool
    description: str


@dataclass(frozen=True)
class PresetSpec:
    name: str
    description: str
    params: tuple[PresetParam, ...] = field(default_factory=tuple)
    requires_graph: bool = True


PRESET_CATALOG: dict[str, PresetSpec] = {
    "recent_champions": PresetSpec(
        name="recent_champions",
        description="Return most recent champions across all strategies, ordered by freeze_date DESC.",
        params=(
            PresetParam("limit", required=False, description="Max results returned (default 20)"),
        ),
        requires_graph=True,
    ),
    "strategy_lineage": PresetSpec(
        name="strategy_lineage",
        description="Return champion lineage rows for a single strategy.",
        params=(
            PresetParam(
                "strategy_id",
                required=True,
                description="Canonical strategy ID (e.g. es-1h-bear-sweep)",
            ),
        ),
        requires_graph=True,
    ),
    "run_history": PresetSpec(
        name="run_history",
        description="Return run history rows for a single strategy, including curator notes.",
        params=(
            PresetParam(
                "strategy_id",
                required=True,
                description="Canonical strategy ID (e.g. es-1h-bear-sweep)",
            ),
        ),
        requires_graph=True,
    ),
    "pending_offline": PresetSpec(
        name="pending_offline",
        description="List artifacts queued for offline graph ingestion (.qws/pending/).",
        params=(),
        requires_graph=False,
    ),
    "downstream_champions": PresetSpec(
        name="downstream_champions",
        description=(
            "Return champions that pivoted from a specific run via explicit PIVOTED_FROM edges. "
            "Returns empty list when no explicit pivot edges exist for the run."
        ),
        params=(
            PresetParam(
                "run_id",
                required=True,
                description="Canonical run ID to query downstream champions for",
            ),
        ),
        requires_graph=True,
    ),
    "staleness_report": PresetSpec(
        name="staleness_report",
        description=(
            "Return Champions frozen more than 30 days ago, ordered by age descending. "
            "Use to identify strategies that need a fresh walk-forward or OOS check."
        ),
        params=(),
        requires_graph=True,
    ),
    "instrument_concentration": PresetSpec(
        name="instrument_concentration",
        description=(
            "Return champion count and total return aggregated by instrument. "
            "Use to detect over-exposure to a single ticker."
        ),
        params=(),
        requires_graph=True,
    ),
    "portfolio_alpha": PresetSpec(
        name="portfolio_alpha",
        description=(
            "Aggregate return and Sharpe across all professional/institutional Champions. "
            "Returns a single row with champion_count, total_return, avg_sharpe, strategies."
        ),
        params=(),
        requires_graph=True,
    ),
    "fragility_report": PresetSpec(
        name="fragility_report",
        description="Return Champions whose fragility list mentions regime sensitivity.",
        params=(),
        requires_graph=True,
    ),
    "list_oos_pending": PresetSpec(
        name="list_oos_pending",
        description=(
            "Return Champions waiting for OOS validation (oos_status = oos_pending), "
            "oldest freeze_date first. Excludes ABORTED strategies."
        ),
        params=(),
        requires_graph=True,
    ),
    "list_aborted": PresetSpec(
        name="list_aborted",
        description=(
            "Return all Strategies with status = ABORTED, including abort_reason. "
            "Ordered by aborted_at DESC. Used before suggesting new strategies."
        ),
        params=(),
        requires_graph=True,
    ),
    "promotion_candidates": PresetSpec(
        name="promotion_candidates",
        description=(
            "Return Run nodes that pass the dual-hurdle significance gate and have no linked "
            "Champion. Hard gates: total_trades >= 30, active_window_frequency >= 0.06. "
            "Ordered by evidence_score (sharpe * sqrt(total_trades)) descending."
        ),
        params=(
            PresetParam(
                "min_sharpe",
                required=False,
                description="Minimum Sharpe ratio (default 2.0)",
            ),
            PresetParam(
                "min_profit_factor",
                required=False,
                description="Minimum profit factor (default 1.3)",
            ),
        ),
        requires_graph=True,
    ),
    "cross_artifact_correlation": PresetSpec(
        name="cross_artifact_correlation",
        description=(
            "Return strategies in the same family. Provide family_id (preferred) for a "
            "direct family scan (Mode B), or strategy_id to anchor on a specific strategy "
            "and resolve its family automatically (Mode A). At least one is required."
        ),
        params=(
            PresetParam(
                "family_id",
                required=False,
                description="12-char family_id hash — preferred; returns all family members (Mode B)",
            ),
            PresetParam(
                "strategy_id",
                required=False,
                description="Anchor strategy ID — resolves family automatically (Mode A)",
            ),
        ),
        requires_graph=True,
    ),
    "research_targets": PresetSpec(
        name="research_targets",
        description=(
            "Return all properties of the singleton ResearchTarget node (promotion thresholds). "
            "Returns one row when seeded, empty when not yet seeded. "
            "Seed with: qw seed --targets"
        ),
        params=(),
        requires_graph=True,
    ),
    "runs_by_regime": PresetSpec(
        name="runs_by_regime",
        description=(
            "Return runs tagged with a specific regime label (via IN_REGIME edge). "
            "Ordered by Sharpe descending. Regime labels are researcher-defined strings "
            "(e.g. high_vol, trend_up, mean_reverting)."
        ),
        params=(
            PresetParam(
                "regime",
                required=True,
                description="Regime label to filter by (e.g. high_vol, trend_down, mean_reverting)",
            ),
        ),
        requires_graph=True,
    ),
    "regime_performance": PresetSpec(
        name="regime_performance",
        description=(
            "Portfolio-wide regime performance table. Groups runs by (strategy, regime) and "
            "computes Regime Diversity Score — count of distinct regimes where the strategy's "
            "best Sharpe met the 2.0 threshold. Score=1 → Regime Specialist (fragility flag). "
            "Score≥3 → Regime Robust. Pass strategy_id to narrow to one strategy."
        ),
        params=(
            PresetParam(
                "strategy_id",
                required=False,
                description="Filter to a single strategy_id (optional)",
            ),
        ),
        requires_graph=True,
    ),
}


def resolve_preset(name: str) -> PresetSpec:
    """Return the PresetSpec for *name* or raise ValueError with a deterministic message."""
    if name not in PRESET_CATALOG:
        available = sorted(PRESET_CATALOG)
        raise ValueError(f"unknown preset: {name!r}. Available: {available}")
    return PRESET_CATALOG[name]


def validate_params(spec: PresetSpec, params: dict[str, str]) -> list[str]:
    """Return a list of validation error strings; empty list means valid."""
    errors: list[str] = []
    allowed = {p.name for p in spec.params}
    required = {p.name for p in spec.params if p.required}

    for name in required:
        if name not in params:
            errors.append(f"missing required param: {name}")

    for name in params:
        if name not in allowed:
            errors.append(f"unknown param: {name!r} (allowed: {sorted(allowed) or 'none'})")

    return errors


def run_preset(
    name: str,
    params: dict[str, str],
    *,
    service: GraphQueryService | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Execute a named preset and return results as a list of flat dicts.

    Raises:
        ValueError: unknown preset name or invalid params.
        RuntimeError: preset requires graph but no service provided.
    """
    spec = resolve_preset(name)

    errors = validate_params(spec, params)
    if errors:
        raise ValueError(f"preset {name!r} param error: {'; '.join(errors)}")

    if spec.requires_graph and service is None:
        raise RuntimeError(f"preset {name!r} requires a graph connection")

    if name == "recent_champions":
        limit = int(params.get("limit", "20"))
        assert service is not None
        return service.get_recent_champions_v1(limit=limit)

    if name == "strategy_lineage":
        strategy_id = params["strategy_id"]
        assert service is not None
        return service.get_strategy_lineage_v1(strategy_id)

    if name == "run_history":
        strategy_id = params["strategy_id"]
        assert service is not None
        return service.get_run_history_v1(strategy_id)

    if name == "pending_offline":
        return _run_pending_offline(repo_root or Path.cwd())

    if name == "downstream_champions":
        run_id = params["run_id"]
        assert service is not None
        return service.get_downstream_champions_v1(run_id)

    if name == "portfolio_alpha":
        assert service is not None
        return service.get_portfolio_alpha_v1()

    if name == "fragility_report":
        assert service is not None
        return service.get_fragility_report_v1()

    if name == "list_oos_pending":
        assert service is not None
        return service.get_list_oos_pending_v1()

    if name == "list_aborted":
        assert service is not None
        return service.get_list_aborted_v1()

    if name == "promotion_candidates":
        min_sharpe = float(params.get("min_sharpe", "2.0"))
        min_profit_factor = float(params.get("min_profit_factor", "1.3"))
        assert service is not None
        return service.get_promotion_candidates_v1(
            min_sharpe=min_sharpe,
            min_profit_factor=min_profit_factor,
        )

    if name == "staleness_report":
        assert service is not None
        return service.get_staleness_report_v1()

    if name == "instrument_concentration":
        assert service is not None
        return service.get_instrument_concentration_v1()

    if name == "cross_artifact_correlation":
        strategy_id = params.get("strategy_id")
        family_id = params.get("family_id")
        if not strategy_id and not family_id:
            raise ValueError(
                "cross_artifact_correlation requires family_id (preferred) or strategy_id"
            )
        assert service is not None
        return service.get_cross_artifact_correlation_v1(
            strategy_id=strategy_id,
            family_id=family_id,
        )

    if name == "research_targets":
        assert service is not None
        return service.get_research_targets_v1()

    if name == "runs_by_regime":
        regime = params["regime"]
        assert service is not None
        return service.get_runs_by_regime_v1(regime=regime)

    if name == "regime_performance":
        assert service is not None
        strategy_id = params.get("strategy_id") or None
        return service.get_regime_performance_v1(strategy_id=strategy_id)

    raise ValueError(f"preset {name!r} has no implementation")  # unreachable


def _run_pending_offline(repo_root: Path) -> list[dict[str, Any]]:
    """List artifacts currently in the offline pending queue."""
    pending_dir = repo_root / ".qws" / "pending"
    if not pending_dir.exists():
        return []

    items: list[dict[str, Any]] = []
    for pending_file in sorted(pending_dir.glob("*.json")):
        try:
            raw: dict[str, Any] = json.loads(pending_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            items.append({"id": pending_file.stem, "kind": None, "artifact_path": None, "error": "unreadable"})
            continue
        items.append({
            "id": pending_file.stem,
            "kind": raw.get("kind"),
            "artifact_path": _extract_artifact_path(raw),
        })

    return items


def _extract_artifact_path(payload: dict[str, Any]) -> str | None:
    """Extract artifact_path from a ResearchArtifact model_dump payload."""
    runs = payload.get("runs")
    if isinstance(runs, list) and runs:
        return runs[0].get("artifact_path")

    champion = payload.get("champion")
    if isinstance(champion, dict):
        return champion.get("artifact_path")

    blob = payload.get("blob")
    if isinstance(blob, dict):
        return blob.get("artifact_path")

    return None


# Convenience re-exports for callers that want to import view functions
# by stable name from the preset layer.
_PRESET_VIEW_FUNCTIONS = {
    "recent_champions": get_recent_champions_v1,
    "strategy_lineage": get_strategy_lineage_v1,
    "run_history": get_run_history_v1,
    "downstream_champions": get_downstream_champions_v1,
    "cross_artifact_correlation": get_cross_artifact_correlation_v1,
    "portfolio_alpha": get_portfolio_alpha_v1,
    "fragility_report": get_fragility_report_v1,
    "staleness_report": get_staleness_report_v1,
    "instrument_concentration": get_instrument_concentration_v1,
    "list_oos_pending": get_list_oos_pending_v1,
    "list_aborted": get_list_aborted_v1,
    "promotion_candidates": get_promotion_candidates_v1,
    "research_targets": get_research_targets_v1,
    "runs_by_regime": get_runs_by_regime_v1,
    "regime_performance": get_regime_performance_v1,
}

__all__ = [
    "PRESET_CATALOG",
    "PresetParam",
    "PresetSpec",
    "resolve_preset",
    "run_preset",
    "validate_params",
]
