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

from .query import get_recent_champions_v1, get_strategy_lineage_v1

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
    "pending_offline": PresetSpec(
        name="pending_offline",
        description="List artifacts queued for offline graph ingestion (.qws/pending/).",
        params=(),
        requires_graph=False,
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

    if name == "pending_offline":
        return _run_pending_offline(repo_root or Path.cwd())

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
}

__all__ = [
    "PRESET_CATALOG",
    "PresetParam",
    "PresetSpec",
    "resolve_preset",
    "run_preset",
    "validate_params",
]
