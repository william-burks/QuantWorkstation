"""MCP Read Adapter — Story 3 / Spike: Lean Neighborhood Optimization.

Read-only contract for MCP tool consumers. All reads route through the Story 1
query layer (``research.graph.query``) via ``GraphQueryService`` public methods.
No file-system artifact parsing occurs in this module.

Policy (from docs/graph_v1_contract.md § MCP Read Contract V1):
- Neo4j-only reads.
- If data is not in graph, MCP does not see it.
- MCP does not parse local files directly.
- No MCP write path in V1.

Tool surface
------------
- ``get_recent_champions(limit)``                      → list of champion detail projections
- ``get_strategy_lineage(strategy_id)``                → list of lineage rows for a strategy
- ``get_context_neighborhood(champion_id, max_runs)``  → bounded champion context neighborhood

Neighborhood bounding (V1 safety cap — Option A)
-------------------------------------------------
``get_context_neighborhood`` fans out to four view functions:

    get_champion_details_v1(champion_id)       → champion
    get_strategy_summary_v1(strategy_id)       → strategy
    get_config_linkage_v1(pivot_from_run_id)   → pivot_config (if present)
    get_run_history_v1(strategy_id)            → recent_runs (capped at max_runs)

Default cap: ``max_runs=50``. Upper bound: 200. If the strategy has more runs than
``max_runs``, the ``runs_capped`` flag in the response is set to ``True``.

Envelope
--------
Every tool method returns a ``McpResult`` with a deterministic ``.to_dict()``
shape::

    {
        "ok": bool,
        "data": <payload> | null,
        "error": {"code": str, "message": str} | null
    }

Error codes
-----------
- ``INVALID_PARAMS`` — caller passed a missing or wrong-type parameter.
- ``INFRA_ERROR``    — Neo4j connection failed or other infrastructure issue.

"Not found" is represented as ``ok=True, data=None`` for single-entity lookups
and ``ok=True, data=[]`` for list lookups. It is not an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from . import ids as _ids

if TYPE_CHECKING:
    from .query import GraphQueryService
    from .store import GraphStore


# ---------------------------------------------------------------------------
# Envelope types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McpError:
    code: Literal["INVALID_PARAMS", "INFRA_ERROR"]
    message: str


@dataclass
class McpResult:
    ok: bool
    data: Any
    error: McpError | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, JSON-serializable representation."""
        return {
            "ok": self.ok,
            "data": self.data,
            "error": (
                {"code": self.error.code, "message": self.error.message}
                if self.error
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Name-based binding: MCP tool → query.py view function
# ---------------------------------------------------------------------------

TOOL_BINDINGS: dict[str, str] = {
    "get_recent_champions": "get_recent_champions_v1",
    "get_strategy_lineage": "get_strategy_lineage_v1",
    # entry point; also fans out to get_strategy_summary_v1 and get_config_linkage_v1
    "get_context_neighborhood": "get_champion_details_v1",
}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class McpReadAdapter:
    """Read-only MCP adapter backed by ``GraphQueryService``.

    Callers should prefer ``from_env()`` for standard configuration, or pass
    an explicit *service* for testing.
    """

    def __init__(self, service: GraphQueryService) -> None:
        self._service = service

    @classmethod
    def from_env(cls, timeout_seconds: int = 3) -> McpReadAdapter:
        from .query import GraphQueryService as _Svc
        return cls(_Svc.from_env(timeout_seconds=timeout_seconds))

    def _get_store(self, timeout_seconds: int = 3) -> GraphStore:
        from .store import GraphStore as _Store
        return _Store.from_env(timeout_seconds=timeout_seconds)

    def close(self) -> None:
        self._service.close()

    # ------------------------------------------------------------------
    # Public tool methods
    # ------------------------------------------------------------------

    def get_recent_champions(self, limit: int = 20) -> McpResult:
        """Return up to *limit* most recent champions ordered by freeze_date DESC.

        Bound to: ``get_recent_champions_v1`` (query.py).
        Never falls back to file-system reads.
        """
        if not isinstance(limit, int) or limit < 1:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message=f"limit must be a positive integer, got {limit!r}",
                ),
            )
        try:
            data = self._service.get_recent_champions_v1(limit=limit)
            return McpResult(ok=True, data=data)
        except Exception as exc:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(code="INFRA_ERROR", message=str(exc)),
            )

    def get_strategy_lineage(self, strategy_id: str) -> McpResult:
        """Return champion lineage rows for *strategy_id*.

        Returns an empty list when the strategy exists but has no champions.
        Returns ``data=[]`` when the strategy_id is unknown — not an error.
        Bound to: ``get_strategy_lineage_v1`` (query.py).
        """
        if not strategy_id or not isinstance(strategy_id, str):
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message="strategy_id must be a non-empty string",
                ),
            )
        try:
            data = self._service.get_strategy_lineage_v1(strategy_id)
            return McpResult(ok=True, data=data)
        except Exception as exc:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(code="INFRA_ERROR", message=str(exc)),
            )

    def get_context_neighborhood(
        self, champion_id: str, max_runs: int = 50
    ) -> McpResult:
        """Return the context neighborhood for a champion.

        Fans out to four view functions::

            get_champion_details_v1(champion_id)       → champion
            get_strategy_summary_v1(strategy_id)       → strategy
            get_config_linkage_v1(pivot_from_run_id)   → pivot_config (if run exists)
            get_run_history_v1(strategy_id)            → recent_runs (capped at max_runs)

        *max_runs* caps the number of run records returned (default 50, max 200).
        When the strategy has more runs than *max_runs*, ``runs_capped`` is ``True``.

        Returns ``data=None`` when *champion_id* is not found in the graph.
        Never reads files.
        Bound entry point: ``get_champion_details_v1`` (query.py).
        """
        if not champion_id or not isinstance(champion_id, str):
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message="champion_id must be a non-empty string",
                ),
            )
        if not isinstance(max_runs, int) or max_runs < 1 or max_runs > 200:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message=f"max_runs must be an integer in 1..200, got {max_runs!r}",
                ),
            )
        try:
            champion = self._service.get_champion_details_v1(champion_id)
            if champion is None:
                return McpResult(ok=True, data=None)

            strategy = self._service.get_strategy_summary_v1(champion["strategy_id"])

            pivot_config: dict[str, Any] | None = None
            pivot_run_id = champion.get("pivot_from_run_id")
            if pivot_run_id:
                pivot_config = self._service.get_config_linkage_v1(pivot_run_id)

            all_runs = self._service.get_run_history_v1(champion["strategy_id"])
            runs_capped = len(all_runs) > max_runs
            recent_runs = all_runs[:max_runs]

            return McpResult(
                ok=True,
                data={
                    "champion": champion,
                    "strategy": strategy,
                    "pivot_config": pivot_config,
                    "recent_runs": recent_runs,
                    "runs_capped": runs_capped,
                },
            )
        except Exception as exc:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(code="INFRA_ERROR", message=str(exc)),
            )


    def log_hypothesis(self, title: str) -> McpResult:
        """Create a Hypothesis node with source='llm' on the SUGGESTED edge.

        Equivalent to ``qw record --hypothesis "<title>"`` but marks source as "llm".
        Returns hypothesis_id on success.
        """
        if not title or not isinstance(title, str):
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message="title must be a non-empty string",
                ),
            )
        if len(title) > 200:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(
                    code="INVALID_PARAMS",
                    message="title must be ≤ 200 characters",
                ),
            )
        try:
            created_at_iso = datetime.now(UTC).isoformat()
            hypothesis_id = _ids.hash12(title, created_at_iso)
            store = self._get_store()
            try:
                store.create_hypothesis(hypothesis_id=hypothesis_id, title=title, source="llm")
            finally:
                store.close()
            return McpResult(
                ok=True,
                data={"hypothesis_id": hypothesis_id, "title": title, "source": "llm"},
            )
        except Exception as exc:
            return McpResult(
                ok=False,
                data=None,
                error=McpError(code="INFRA_ERROR", message=str(exc)),
            )


__all__ = [
    "TOOL_BINDINGS",
    "McpError",
    "McpReadAdapter",
    "McpResult",
]
