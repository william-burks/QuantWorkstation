"""Neo4j store layer for idempotent Graph V1 writes."""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from . import ids as _ids
from .analyst import truncate_curator_note
from .cypher import (
    ABORT_STRATEGY_QUERY,
    AUDIT_NULL_FAMILY_ID_QUERY,
    BLOB_INGEST_QUERY,
    CHAMPION_INGEST_QUERY,
    CORRELATED_WITH_CHAMPION_QUERY,
    CORRELATED_WITH_STRATEGY_QUERY,
    CSV_INGEST_QUERY,
    DEMO_SEED_CYPHER,
    DEMO_TEARDOWN_CYPHER,
    ENSURE_RESEARCH_TARGET_QUERY,
    GET_ALL_HYPOTHESIS_EMBEDDINGS_QUERY,
    GET_CHAMPION_OOS_STATUS_QUERY,
    GET_HYPOTHESES_WITHOUT_EMBEDDINGS_QUERY,
    GET_HYPOTHESIS_BY_ID_QUERY,
    GET_PORTFOLIO_ALPHA_CHAMPIONS_QUERY,
    HYPOTHESIS_BRANCHED_FROM_QUERY,
    HYPOTHESIS_CREATE_QUERY,
    HYPOTHESIS_SET_EMBEDDING_QUERY,
    HYPOTHESIS_SUGGESTED_EDGE_QUERY,
    HYPOTHESIS_TESTED_AS_QUERY,
    HYPOTHESIS_UPDATE_STATUS_QUERY,
    PATCH_FAMILY_ID_QUERY,
    PATCH_RESEARCH_TARGET_QUERY,
    PATCH_RUN_HTML_PATH_QUERY,
    REGIME_MERGE_QUERY,
    RUN_REDUNDANCY_CHECK_CYPHER,
    RUN_STATS_SUMMARY_QUERY,
    SEMANTICALLY_RELATED_MERGE_QUERY,
    UPDATE_CHAMPION_OOS_STATUS_QUERY,
)
from .models import ResearchArtifact, RunStatsSummary

_PROFESSIONAL_SHARPE_THRESHOLD = 2.0
_INSTITUTIONAL_SHARPE_THRESHOLD = 3.5

_RESEARCH_TARGET_DEFAULTS: dict[str, float | int] = {
    "sharpe_professional": 2.0,
    "sharpe_institutional": 3.5,
    "max_holding_hours": 4,
    "min_trades": 30,
    "min_active_window_frequency": 0.06,
    "profit_factor_min": 1.3,
    "calmar_min": 1.5,
    "max_drawdown_floor": -0.20,
    "correlation_gate": 0.30,
}

RESEARCH_TARGET_ALLOWED_KEYS: frozenset[str] = frozenset(_RESEARCH_TARGET_DEFAULTS)


class StoreError(RuntimeError):
    """Base store exception."""


class StoreInfraError(StoreError):
    """Raised when Neo4j connectivity or execution fails."""


@dataclass(frozen=True)
class EvolutionOutcome:
    """Per-run outcome from the evolutionary dedup gate."""

    run_id: str
    status: str  # "skipped" | "recorded" | "promoted"
    reason: str  # non-empty for skipped; describes why it was suppressed
    evidence_score: float | None  # sharpe * sqrt(total_trades); None when not computable
    champion_id: str | None = None  # set when this run was auto-promoted to Champion


@dataclass(frozen=True)
class StoreResult:
    """Store write result used for receipts and CLI output."""

    status: str
    node_counts: dict[str, int]
    relationship_counts: dict[str, int]
    evolution: list[EvolutionOutcome] = field(default_factory=list)


class GraphStore:
    """Applies contract MERGE mappings in one transaction per artifact."""

    def __init__(self, uri: str, username: str, password: str, timeout_seconds: int = 3, database: str = "neo4j"):
        self._database = database
        self._driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=timeout_seconds,
            max_connection_lifetime=300,
        )

    @classmethod
    def from_env(cls, timeout_seconds: int = 3) -> GraphStore:
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

    def ping(self) -> None:
        """Verify connectivity with configured timeout."""
        try:
            self._driver.verify_connectivity()
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Neo4j connectivity check failed: {exc}") from exc

    def persist_artifact(
        self,
        artifact: ResearchArtifact,
        summary: RunStatsSummary | None = None,
    ) -> StoreResult:
        payload = artifact.model_dump(mode="json")

        try:
            with self._driver.session(database=self._database) as session:
                if artifact.kind in {"baseline_csv", "grid_csv"}:
                    strategy_id = artifact.strategy.strategy_id
                    evolution_outcomes: list[EvolutionOutcome] = []
                    skipped_run_ids: set[str] = set()

                    # Pre-check: redundancy gate per run
                    for run_d in payload["runs"]:
                        run_id = run_d["run_id"]
                        total_trades = int(run_d.get("total_trades") or 0)
                        sharpe = float(run_d.get("sharpe") or 0.0)
                        timestamp_iso = run_d.get("timestamp", "")

                        is_redundant = self._check_run_redundancy(
                            session, strategy_id, run_id, total_trades, sharpe, timestamp_iso
                        )

                        if is_redundant:
                            ev = sharpe * (total_trades ** 0.5) if total_trades > 0 else 0.0
                            evolution_outcomes.append(EvolutionOutcome(
                                run_id=run_id,
                                status="skipped",
                                reason=(
                                    f"existing run with total_trades={total_trades} "
                                    f"has sharpe >= {sharpe:.3f} within 30 days"
                                ),
                                evidence_score=ev,
                            ))
                            skipped_run_ids.add(run_id)

                    # Build filtered payload (drop redundant runs)
                    if skipped_run_ids:
                        paired = list(zip(payload["runs"], payload["configs"]))
                        kept = [(r, c) for r, c in paired if r["run_id"] not in skipped_run_ids]
                        if not kept:
                            # Reconcile champion for existing best run (retroactive fix)
                            self._reconcile_champion(session, strategy_id)
                            return StoreResult(
                                status="skipped",
                                node_counts={"Run": 0},
                                relationship_counts={},
                                evolution=evolution_outcomes,
                            )
                        kept_runs, kept_configs = zip(*kept)
                        filtered_payload: dict = {
                            **payload,
                            "runs": list(kept_runs),
                            "configs": list(kept_configs),
                        }
                    else:
                        filtered_payload = payload

                    # Write non-redundant rows
                    self._persist_csv(session, filtered_payload, summary)

                    # Post-write: evidence score promotion
                    best_run_id, best_ev, displaced_run_id = self._update_best_run(
                        session, strategy_id
                    )

                    # Always reconcile champion — works for new peaks and retroactive gaps
                    auto_champion_id: str | None = self._reconcile_champion(session, strategy_id)

                    for run_d in filtered_payload["runs"]:
                        run_id = run_d["run_id"]
                        t = int(run_d.get("total_trades") or 0)
                        s = float(run_d.get("sharpe") or 0.0)
                        ev = s * (t ** 0.5) if t > 0 else 0.0
                        is_promoted = run_id == best_run_id
                        evolution_outcomes.append(EvolutionOutcome(
                            run_id=run_id,
                            status="promoted" if is_promoted else "recorded",
                            reason="",
                            evidence_score=ev,
                            champion_id=auto_champion_id if is_promoted else None,
                        ))

                    n_written = len(filtered_payload["runs"])
                    node_counts: dict[str, int] = {
                        "Strategy": 1,
                        "Run": n_written,
                        "Config": n_written,
                    }
                    rel_counts: dict[str, int] = {
                        "HAS_RUN": n_written,
                        "USES_CONFIG": n_written,
                    }
                    if summary is not None and n_written > 0:
                        node_counts["RunStatsSummary"] = 1
                        rel_counts["HAS_RUN_SUMMARY"] = 1
                    return StoreResult(
                        status="persisted",
                        node_counts=node_counts,
                        relationship_counts=rel_counts,
                        evolution=evolution_outcomes,
                    )

                if artifact.kind == "champion_md":
                    champion_tier = str(
                        (payload.get("champion") or {})
                        .get("metrics_summary", {})
                        .get("tier", "")
                    ).lower()
                    if champion_tier == "fail":
                        return StoreResult(
                            status="skipped",
                            node_counts={"Champion": 0},
                            relationship_counts={},
                        )
                    self._persist_champion(session, payload)
                    rel_counts = {"PRODUCED_CHAMPION": 1}
                    if artifact.champion and artifact.champion.pivot_from_run_id:
                        rel_counts["PIVOTED_FROM"] = 1
                    return StoreResult(
                        status="persisted",
                        node_counts={"Strategy": 1, "Champion": 1},
                        relationship_counts=rel_counts,
                    )

                if artifact.kind == "tracker_md":
                    self._persist_blob(session, payload)
                    return StoreResult(
                        status="persisted",
                        node_counts={"Strategy": 1, "BlobArtifact": 1},
                        relationship_counts={"HAS_BLOB": 1},
                    )

                raise StoreError(f"Unsupported artifact kind: {artifact.kind}")

        except StoreError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def abort_strategy(self, strategy_id: str, reason: str) -> bool:
        """Mark a strategy as ABORTED with an explicit reason.

        Returns ``True`` when the strategy was found and updated, ``False`` when
        no ``Strategy`` node with that ``strategy_id`` exists.  Raises
        ``StoreInfraError`` on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx):
                    result = tx.run(ABORT_STRATEGY_QUERY, strategy_id=strategy_id, reason=reason)
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def audit_null_family_ids(self) -> list[dict]:
        """Return all Strategy nodes that have no family_id set.

        Used to identify which nodes need backfill before running
        ``patch_family_id``.  Returns a list of dicts with keys
        ``strategy_id``, ``logic_type``, ``direction``, ``created_at``.

        Raises ``StoreInfraError`` on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx):
                    return [dict(r) for r in tx.run(AUDIT_NULL_FAMILY_ID_QUERY)]

                return session.execute_read(_read)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def patch_family_id(self, strategy_id: str, family_id: str) -> bool:
        """Set family_id on a Strategy node directly (Path B backfill).

        Idempotent — safe to re-run with the same values.  Returns ``True``
        when the strategy was found and updated, ``False`` when no
        ``Strategy`` node with that ``strategy_id`` exists.

        Raises ``StoreInfraError`` on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx):
                    result = tx.run(PATCH_FAMILY_ID_QUERY, strategy_id=strategy_id, family_id=family_id)
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def patch_run_html_path(self, run_id: str, html_path: str) -> bool:
        """Attach an HTML report path to an existing Run node.

        Idempotent — repeated calls with the same path are safe.  Repeated
        calls with a different path overwrite the previous value (re-run
        replaces the report pointer).  Returns ``True`` when the Run node was
        found and updated, ``False`` when no ``Run`` node with that
        ``run_id`` exists (e.g., the run was deduplicated/skipped).

        Raises ``StoreInfraError`` on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx):
                    result = tx.run(PATCH_RUN_HTML_PATH_QUERY, run_id=run_id, html_path=html_path)
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def update_champion_oos_status(
        self,
        champion_id: str,
        status: str,
        oos_date: str | None = None,
        sharpe: float | None = None,
    ) -> bool:
        """Update oos_status, oos_date, and optionally metrics_oos_sharpe on a Champion node.

        Args:
            champion_id: Target Champion node ID.
            status: New oos_status value.
            oos_date: ISO date; defaults to today.
            sharpe: OOS Sharpe ratio. Stored as ``metrics_oos_sharpe`` when not None.

        Returns ``True`` when the champion was found and updated, ``False`` when no
        ``Champion`` node with that ``champion_id`` exists.

        Raises ``StoreError`` when the champion currently carries
        ``oos_status = 'retired'`` — that is a lifecycle state, not an OOS outcome.
        Raises ``StoreInfraError`` on Neo4j connectivity or execution failure.
        """
        from datetime import date as _date

        resolved_date = oos_date or _date.today().isoformat()

        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx):
                    result = tx.run(GET_CHAMPION_OOS_STATUS_QUERY, champion_id=champion_id).single()
                    return result

                row = session.execute_read(_read)
                if row is None:
                    return False

                current_oos = row["oos_status"]
                if current_oos == "retired":
                    raise StoreError(
                        f"Champion {champion_id!r} has lifecycle status 'retired'; "
                        "use qw retire instead"
                    )

                def _write(tx):
                    result = tx.run(
                        UPDATE_CHAMPION_OOS_STATUS_QUERY,
                        champion_id=champion_id,
                        oos_status=status,
                        oos_date=resolved_date,
                        oos_sharpe=sharpe,
                    )
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0

        except StoreError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def ensure_research_target(
        self,
        overrides: dict[str, float | int] | None = None,
    ) -> None:
        """Create or update the singleton ResearchTarget node.

        On first call: creates the node with all default values.
        On subsequent calls with no overrides: idempotent — only ``updated_at`` changes.
        On calls with overrides: applies each key=value pair on top of existing values.

        Raises:
            ValueError: When overrides contains keys not in RESEARCH_TARGET_ALLOWED_KEYS.
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        if overrides:
            unknown = set(overrides) - RESEARCH_TARGET_ALLOWED_KEYS
            if unknown:
                raise ValueError(
                    f"Unknown ResearchTarget keys: {sorted(unknown)}. "
                    f"Allowed: {sorted(RESEARCH_TARGET_ALLOWED_KEYS)}"
                )

        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx) -> None:
                    tx.run(ENSURE_RESEARCH_TARGET_QUERY, **_RESEARCH_TARGET_DEFAULTS).consume()
                    if overrides:
                        tx.run(PATCH_RESEARCH_TARGET_QUERY, overrides=overrides).consume()

                session.execute_write(_write)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def seed_demo_graph(self) -> None:
        """Populate deterministic demo nodes for query preset validation.

        Idempotent — uses MERGE throughout. All nodes carry ``is_demo=true``
        so they can be removed cleanly via :meth:`teardown_demo_graph`.

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                session.execute_write(lambda tx: tx.run(DEMO_SEED_CYPHER).consume())
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def teardown_demo_graph(self) -> None:
        """Remove all nodes where ``is_demo=true`` and their relationships.

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                session.execute_write(lambda tx: tx.run(DEMO_TEARDOWN_CYPHER).consume())
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    # ---------------------------------------------------------------------------
    # Hypothesis journaling (QWS-0601)
    # ---------------------------------------------------------------------------

    def create_hypothesis(self, hypothesis_id: str, title: str, source: str = "user") -> str:
        """Create a Hypothesis node and SUGGESTED edge.

        Idempotent — MERGE on hypothesis_id.

        Args:
            hypothesis_id: Deterministic 12-char hex ID.
            title: Short description (≤ 200 chars).
            source: "user" for CLI; "llm" for MCP.

        Returns:
            hypothesis_id on success.

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx) -> str:
                    tx.run(HYPOTHESIS_CREATE_QUERY, hypothesis_id=hypothesis_id, title=title).consume()
                    tx.run(HYPOTHESIS_SUGGESTED_EDGE_QUERY, hypothesis_id=hypothesis_id, source=source).consume()
                    return hypothesis_id

                return session.execute_write(_write)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def link_hypothesis_tested_as(self, hypothesis_id: str, strategy_id: str) -> bool:
        """Create TESTED_AS edge from Hypothesis to Strategy.

        Returns True when both nodes exist and edge was created/confirmed,
        False when hypothesis not found, raises StoreError when strategy not found.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _check_strategy(tx) -> bool:
                    result = tx.run(
                        "MATCH (s:Strategy {strategy_id: $strategy_id}) RETURN s.strategy_id AS sid",
                        strategy_id=strategy_id,
                    ).single()
                    return result is not None

                def _write(tx):
                    result = tx.run(
                        HYPOTHESIS_TESTED_AS_QUERY,
                        hypothesis_id=hypothesis_id,
                        strategy_id=strategy_id,
                    )
                    return list(result)

                strategy_exists = session.execute_read(_check_strategy)
                if not strategy_exists:
                    raise StoreError(f"Strategy {strategy_id!r} not found in graph")

                records = session.execute_write(_write)
                return len(records) > 0

        except StoreError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def link_hypothesis_branched_from(
        self,
        hypothesis_id: str,
        node_id: str,
        rationale: str,
    ) -> bool:
        """Create BRANCHED_FROM edge from Hypothesis to any node.

        Returns True when edge created, False when hypothesis not found.
        Raises StoreError when target node not found.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _check_node(tx) -> bool:
                    result = tx.run(
                        """
                        MATCH (n)
                        WHERE n.hypothesis_id = $node_id
                          OR n.strategy_id = $node_id
                          OR n.run_id = $node_id
                          OR n.champion_id = $node_id
                          OR n.regime_id = $node_id
                        RETURN count(n) > 0 AS found
                        LIMIT 1
                        """,
                        node_id=node_id,
                    ).single()
                    return bool(result["found"]) if result is not None else False

                def _write(tx):
                    result = tx.run(
                        HYPOTHESIS_BRANCHED_FROM_QUERY,
                        hypothesis_id=hypothesis_id,
                        node_id=node_id,
                        rationale=rationale,
                    )
                    return list(result)

                node_exists = session.execute_read(_check_node)
                if not node_exists:
                    raise StoreError(f"Target node {node_id!r} not found in graph")

                records = session.execute_write(_write)
                return len(records) > 0

        except StoreError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def update_hypothesis_status(self, hypothesis_id: str, status: str) -> bool:
        """Update status on a Hypothesis node.

        Returns True when found and updated, False when not found.
        Raises ValueError for invalid status values.
        """
        _VALID_HYPOTHESIS_STATUSES = frozenset({"open", "confirmed", "refuted", "abandoned"})
        if status not in _VALID_HYPOTHESIS_STATUSES:
            raise ValueError(
                f"invalid hypothesis status {status!r}; must be one of: "
                f"{sorted(_VALID_HYPOTHESIS_STATUSES)}"
            )
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx):
                    result = tx.run(
                        HYPOTHESIS_UPDATE_STATUS_QUERY,
                        hypothesis_id=hypothesis_id,
                        status=status,
                    )
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0

        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def hypothesis_exists(self, hypothesis_id: str) -> bool:
        """Return True when a Hypothesis node with this ID exists."""
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx) -> bool:
                    result = tx.run(
                        GET_HYPOTHESIS_BY_ID_QUERY,
                        hypothesis_id=hypothesis_id,
                    ).single()
                    return result is not None

                return session.execute_read(_read)

        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    # ---------------------------------------------------------------------------
    # Portfolio correlation (QWS-0603)
    # ---------------------------------------------------------------------------

    def write_correlated_with(
        self,
        champion_id_a: str,
        strategy_id_a: str,
        champion_id_b: str,
        strategy_id_b: str,
        coefficient: float,
        threshold: float,
        lookback: str = "full",
    ) -> None:
        """Write symmetric CORRELATED_WITH edges for a Champion pair and their parent Strategies.

        Idempotent — uses MERGE with pair_key so re-running the script produces no duplicates.
        pair_key is the sorted concatenation of the two IDs joined by pipe.

        Args:
            champion_id_a: First Champion node ID.
            strategy_id_a: Parent Strategy ID of champion_id_a.
            champion_id_b: Second Champion node ID.
            strategy_id_b: Parent Strategy ID of champion_id_b.
            coefficient:   Pearson correlation coefficient.
            threshold:     Threshold used during computation.
            lookback:      Descriptive lookback label (e.g. "full", "1y").

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        ids = sorted([champion_id_a, champion_id_b])
        pair_key_champ = f"{ids[0]}|{ids[1]}"
        sids = sorted([strategy_id_a, strategy_id_b])
        pair_key_strat = f"{sids[0]}|{sids[1]}"

        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx) -> None:  # type: ignore[no-untyped-def]
                    tx.run(
                        CORRELATED_WITH_CHAMPION_QUERY,
                        champion_id_a=champion_id_a,
                        champion_id_b=champion_id_b,
                        pair_key=pair_key_champ,
                        coefficient=coefficient,
                        threshold=threshold,
                        lookback=lookback,
                    ).consume()
                    tx.run(
                        CORRELATED_WITH_STRATEGY_QUERY,
                        strategy_id_a=strategy_id_a,
                        strategy_id_b=strategy_id_b,
                        pair_key=pair_key_strat,
                        coefficient=coefficient,
                        threshold=threshold,
                        lookback=lookback,
                    ).consume()

                session.execute_write(_write)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def get_portfolio_alpha_champions(self) -> list[dict[str, object]]:
        """Return OOS-pass Champions with artifact_path for correlation computation.

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
                    return [dict(r["result"]) for r in tx.run(GET_PORTFOLIO_ALPHA_CHAMPIONS_QUERY)]

                return session.execute_read(_read)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def check_correlated_with_active_champions(
        self,
        candidate_champion_id: str,
        threshold: float = 0.60,
    ) -> list[dict[str, object]]:
        """Return active Champions that have a CORRELATED_WITH edge to *candidate_champion_id*.

        Used by the correlation gate in `qw record --bundle` auto-promote path.

        Returns a list of dicts with keys: champion_id, strategy_id, coefficient.
        Empty list means no high-correlation overlap.

        Raises:
            StoreInfraError: On Neo4j connectivity or execution failure.
        """
        _CORR_GATE_CYPHER = """
MATCH (cand:Champion {champion_id: $candidate_id})
MATCH (cand)-[e:CORRELATED_WITH]->(other:Champion)
WHERE e.coefficient >= $threshold
  AND other.champion_id <> $candidate_id
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(other)
WHERE s.status <> 'ABORTED'
RETURN {
  champion_id: other.champion_id,
  strategy_id: other.strategy_id,
  coefficient: e.coefficient
} AS result
"""
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
                    return [
                        dict(r["result"])
                        for r in tx.run(
                            _CORR_GATE_CYPHER,
                            candidate_id=candidate_champion_id,
                            threshold=threshold,
                        )
                    ]

                return session.execute_read(_read)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def _check_run_redundancy(
        self,
        session,
        strategy_id: str,
        run_id: str,
        total_trades: int,
        sharpe: float,
        timestamp_iso: str,
    ) -> bool:
        """Return True if an existing run makes this one redundant.

        Redundant = same ``total_trades``, existing sharpe >= new sharpe, and
        the timestamps are within 30 days of each other.  The 30-day exception
        preserves longitudinal walk-forward data while suppressing re-ingests
        that add no statistical information.

        The run is excluded from its own comparison (by ``run_id``) so
        re-ingesting the same file is idempotent.
        """
        def _read(tx):
            result = tx.run(
                RUN_REDUNDANCY_CHECK_CYPHER,
                strategy_id=strategy_id,
                new_run_id=run_id,
                new_trades=total_trades,
                new_sharpe=sharpe,
                new_timestamp=timestamp_iso,
            ).single()
            return bool(result["is_redundant"]) if result is not None else False

        return session.execute_read(_read)

    def _update_best_run(
        self,
        session,
        strategy_id: str,
    ) -> tuple[str | None, float | None, str | None]:
        """Promote the highest evidence-score run to ``Strategy.best_run_id``.

        Evidence score = sharpe × √total_trades.  Archives the previous best
        run by setting ``Run.peaked_as_best = true`` when it is displaced.

        Returns ``(best_run_id, evidence_score, displaced_run_id)``.
        ``displaced_run_id`` is non-None only when a different run held the
        top spot before this call.
        """
        def _read(tx):
            s_row = tx.run(
                "MATCH (s:Strategy {strategy_id: $sid}) RETURN s.best_run_id AS brid",
                sid=strategy_id,
            ).single()
            old_best = s_row["brid"] if s_row else None

            best = tx.run(
                "MATCH (s:Strategy {strategy_id: $sid})-[:HAS_RUN]->(r:Run) "
                "WHERE r.total_trades IS NOT NULL AND r.total_trades > 0 "
                "  AND r.sharpe IS NOT NULL "
                "WITH r, (r.sharpe * sqrt(toFloat(r.total_trades))) AS ev "
                "ORDER BY ev DESC LIMIT 1 "
                "RETURN r.run_id AS run_id, ev AS evidence_score",
                sid=strategy_id,
            ).single()

            return old_best, best

        old_best_run_id, best_row = session.execute_read(_read)

        if best_row is None:
            return None, None, None

        new_best_run_id: str = best_row["run_id"]
        evidence_score = float(best_row["evidence_score"])
        displaced = (
            old_best_run_id
            if old_best_run_id and old_best_run_id != new_best_run_id
            else None
        )

        def _write(tx) -> None:
            if displaced:
                tx.run(
                    "MATCH (r:Run {run_id: $run_id}) SET r.peaked_as_best = true",
                    run_id=displaced,
                ).consume()
            tx.run(
                "MATCH (s:Strategy {strategy_id: $sid}) "
                "SET s.best_run_id = $best_run_id, "
                "    s.best_evidence_score = $ev, "
                "    s.updated_at = datetime()",
                sid=strategy_id,
                best_run_id=new_best_run_id,
                ev=evidence_score,
            ).consume()

        session.execute_write(_write)

        return new_best_run_id, evidence_score, displaced

    def _maybe_auto_promote_champion(
        self,
        session,
        strategy_id: str,
        run_data: dict,
        evidence_score: float,
    ) -> str | None:
        """Auto-promote a newly-written run to Champion if it sets a new evidence peak.

        Quality gate: run's Sharpe must be >= PROFESSIONAL threshold (2.0).
        When promotion happens:
          - The existing ``PRODUCED_CHAMPION`` relationship is relabelled to
            ``WAS_CHAMPION`` (lineage preserved, hidden from active queries).
          - A new Champion node is created with the run's metrics.
          - A new ``PRODUCED_CHAMPION`` relationship is created.
          - A ``PIVOTED_FROM`` edge links the Champion to the promoted Run.

        Returns the new ``champion_id`` when promotion occurred, else ``None``.
        """
        tier_raw = str(run_data.get("tier", "")).lower()
        if tier_raw == "fail":
            return None

        sharpe = float(run_data.get("sharpe") or 0.0)
        if sharpe < _PROFESSIONAL_SHARPE_THRESHOLD:
            return None

        run_id = run_data["run_id"]

        # Read current champion's evidence score (if any)
        def _read(tx):
            result = tx.run(
                """
                MATCH (s:Strategy {strategy_id: $sid})-[:PRODUCED_CHAMPION]->(ch:Champion)
                RETURN ch.champion_id AS champion_id,
                       ch.auto_promoted AS auto_promoted,
                       COALESCE(
                         ch.best_evidence_score,
                         ch.metrics_sharpe * sqrt(toFloat(COALESCE(ch.metrics_total_trades, 0)))
                       ) AS evidence_score
                ORDER BY ch.freeze_date DESC LIMIT 1
                """,
                sid=strategy_id,
            ).single()
            return result

        current = session.execute_read(_read)

        # Compute the champion_id we'd create — deterministic from (strategy, run).
        new_champ_id = _ids.hash12(strategy_id, run_id)

        # Fast idempotency exit: if the current champion IS this run, nothing to do.
        if current is not None and current["champion_id"] == new_champ_id:
            return new_champ_id

        # Respect human curation: a manually-ingested champion_md should never be
        # silently overridden by the auto-promote gate.  If the researcher has curated
        # a champion, a new champion_md is the correct path for the next version.
        if current is not None and not current.get("auto_promoted"):
            return None

        # Gate: only promote if new evidence strictly beats the current auto-promoted champion.
        if current is not None:
            old_ev = float(current["evidence_score"] or 0.0)
            if evidence_score <= old_ev:
                return None

        # Compute tier and build champion payload
        tier = "institutional" if sharpe >= _INSTITUTIONAL_SHARPE_THRESHOLD else "professional"
        today_iso = datetime.date.today().isoformat()
        total_trades = int(run_data.get("total_trades") or 0)
        total_r = float(run_data.get("total_r") or 0.0)
        metrics_return = float(run_data.get("metrics_return") or 0.0)
        profit_factor = float(run_data.get("profit_factor") or 0.0)
        win_rate = float(run_data.get("win_rate") or 0.0)
        max_drawdown = float(run_data.get("max_drawdown") or 0.0)
        artifact_path = run_data.get("artifact_path", "")
        metrics_summary_text = json.dumps(
            {
                "auto_promoted": True,
                "max_drawdown_r": max_drawdown,
                "profit_factor": profit_factor,
                "return": total_r,
                "sample_size": total_trades,
                "sharpe": sharpe,
                "tier": tier,
                "total_trades": total_trades,
                "win_rate": win_rate,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        def _write(tx) -> None:
            # Combined: retire existing champion (label swap + delete old rel),
            # create new Champion, chain new → retired via WAS_CHAMPION.
            tx.run(
                """
                MATCH (s:Strategy {strategy_id: $sid})
                OPTIONAL MATCH (s)-[old:PRODUCED_CHAMPION]->(prev:Champion)

                FOREACH (rel IN CASE WHEN old IS NULL THEN [] ELSE [old] END |
                  DELETE rel
                )
                FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
                  REMOVE prev:Champion
                  SET prev:RetiredChampion
                )

                // WITH required between FOREACH and MATCH in Cypher.
                // Carry prev through so the WAS_CHAMPION chain write below works.
                WITH s, prev
                // Re-label any existing RetiredChampion with this ID so the
                // MERGE below finds it rather than creating a duplicate node.
                OPTIONAL MATCH (rc:RetiredChampion {champion_id: $champion_id})
                FOREACH (_ IN CASE WHEN rc IS NULL THEN [] ELSE [1] END |
                  SET rc:Champion
                  REMOVE rc:RetiredChampion
                )

                MERGE (ch:Champion {champion_id: $champion_id})
                  ON CREATE SET ch.created_at = datetime()
                  SET
                    ch.strategy_id = $sid,
                    ch.freeze_date = date($freeze_date),
                    ch.tier = $tier,
                    ch.metrics_summary = $metrics_summary,
                    ch.metrics_sharpe = $sharpe,
                    ch.metrics_total_trades = $total_trades,
                    ch.metrics_return = $metrics_return,
                    ch.metrics_profit_factor = $profit_factor,
                    ch.metrics_win_rate = $win_rate,
                    ch.metrics_max_drawdown_r = $max_drawdown,
                    ch.best_evidence_score = $evidence_score,
                    ch.oos_status = 'oos_pending',
                    ch.fragilities = $fragilities,
                    ch.artifact_path = $artifact_path,
                    ch.auto_promoted = true,
                    ch.updated_at = datetime()

                MERGE (s)-[:PRODUCED_CHAMPION]->(ch)
                FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
                  CREATE (ch)-[:WAS_CHAMPION]->(prev)
                )

                WITH ch
                MATCH (r:Run {run_id: $run_id})
                MERGE (ch)-[:PIVOTED_FROM]->(r)
                """,
                sid=strategy_id,
                champion_id=new_champ_id,
                freeze_date=today_iso,
                tier=tier,
                metrics_summary=metrics_summary_text,
                sharpe=sharpe,
                total_trades=total_trades,
                total_r=total_r,
                metrics_return=metrics_return,
                profit_factor=profit_factor,
                win_rate=win_rate,
                max_drawdown=max_drawdown,
                evidence_score=evidence_score,
                fragilities=[
                    f"Auto-promoted via evidence gate — run_id={run_id}, "
                    f"evidence_score={evidence_score:.2f} — no OOS validation performed",
                    "Single promotion cycle; lineage preserved via WAS_CHAMPION edges",
                ],
                artifact_path=artifact_path,
                run_id=run_id,
            ).consume()

        session.execute_write(_write)
        return new_champ_id

    def _reconcile_champion(self, session, strategy_id: str) -> str | None:
        """Enforce One Strategy = One Champion, then ensure the current peak is reflected.

        Step 1 — Flatten: if multiple PRODUCED_CHAMPION edges exist (stale state),
        retire all but the highest-evidence one atomically.  Each demoted node has its
        :Champion label swapped to :RetiredChampion and a WAS_CHAMPION edge created
        from the surviving king.

        Step 2 — Auto-promote: reads the highest evidence-score Run and delegates
        to :meth:`_maybe_auto_promote_champion`.  Safe to call unconditionally —
        returns ``None`` when the quality gate blocks promotion or the current
        champion already holds the peak.
        """
        def _flatten(tx) -> None:
            tx.run(
                """
                MATCH (s:Strategy {strategy_id: $sid})-[rel:PRODUCED_CHAMPION]->(c:Champion)
                WITH s, rel, c,
                     COALESCE(
                       c.best_evidence_score,
                       c.metrics_sharpe * sqrt(toFloat(COALESCE(c.metrics_total_trades, 0)))
                     ) AS ev
                ORDER BY ev DESC
                WITH s, collect(c) AS champs, collect(rel) AS rels
                WITH s, champs[0] AS king, champs[1..] AS losers, rels[1..] AS loser_rels
                WHERE size(losers) > 0
                UNWIND range(0, size(losers) - 1) AS i
                WITH s, king, losers[i] AS loser, loser_rels[i] AS loser_rel
                DELETE loser_rel
                REMOVE loser:Champion
                SET loser:RetiredChampion
                CREATE (king)-[:WAS_CHAMPION]->(loser)
                """,
                sid=strategy_id,
            ).consume()

        session.execute_write(_flatten)

        def _read(tx):
            return tx.run(
                "MATCH (s:Strategy {strategy_id: $sid})-[:HAS_RUN]->(r:Run) "
                "WHERE r.total_trades IS NOT NULL AND r.total_trades > 0 "
                "  AND r.sharpe IS NOT NULL "
                "WITH r, (r.sharpe * sqrt(toFloat(r.total_trades))) AS ev "
                "ORDER BY ev DESC LIMIT 1 "
                "RETURN r.run_id AS run_id, r.sharpe AS sharpe, "
                "       r.profit_factor AS profit_factor, r.win_rate AS win_rate, "
                "       r.max_drawdown AS max_drawdown, r.total_trades AS total_trades, "
                "       r.total_r AS total_r, r.metrics_return AS metrics_return, "
                "       r.artifact_path AS artifact_path, "
                "       ev AS evidence_score",
                sid=strategy_id,
            ).single()

        best = session.execute_read(_read)
        if best is None:
            return None

        run_data = {
            "run_id": best["run_id"],
            "sharpe": float(best["sharpe"] or 0.0),
            "profit_factor": float(best["profit_factor"] or 0.0),
            "win_rate": float(best["win_rate"] or 0.0),
            "max_drawdown": float(best["max_drawdown"] or 0.0),
            "total_trades": int(best["total_trades"] or 0),
            "total_r": float(best["total_r"] or 0.0),
            "metrics_return": float(best.get("metrics_return") or 0.0),
            "artifact_path": best["artifact_path"] or "",
        }
        return self._maybe_auto_promote_champion(
            session, strategy_id, run_data, float(best["evidence_score"] or 0.0)
        )

    def _persist_csv(self, session, payload: dict, summary: RunStatsSummary | None = None) -> None:
        rows = []
        strategy_payload = payload["strategy"]
        for run_payload, config_payload in zip(payload["runs"], payload["configs"], strict=True):
            _sharpe = float(run_payload.get("sharpe") or 0.0)
            _trades = int(run_payload.get("total_trades") or 0)
            _ev = _sharpe * (_trades ** 0.5) if _trades > 0 else 0.0
            run_for_query = {
                **run_payload,
                "curator_note": truncate_curator_note(run_payload.get("curator_note")) or "",
                "evidence_score": _ev,
            }
            params_dict = config_payload.get("params_json", {})
            config_for_query = {
                **config_payload,
                "params_json_text": json.dumps(params_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                "risk_params_text": json.dumps(config_payload.get("risk_params", {}), sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                # First-class Config properties: unpacked by SET c += row.config.params_dict
                "params_dict": params_dict,
            }
            rows.append(
                {
                    "strategy": strategy_payload,
                    "run": run_for_query,
                    "config": config_for_query,
                }
            )

        regime_rows = [
            {"run_id": row["run"]["run_id"], "regime_id": row["run"]["regime"]}
            for row in rows
            if row["run"].get("regime")
        ]

        def _write(tx) -> None:
            tx.run(CSV_INGEST_QUERY, rows=rows).consume()
            if regime_rows:
                tx.run(REGIME_MERGE_QUERY, regime_rows=regime_rows).consume()
            if summary is not None:
                result = tx.run(
                    "MATCH (:Strategy {strategy_id: $sid})-[:HAS_RUN_SUMMARY]->(rss:RunStatsSummary) "
                    "RETURN coalesce(max(rss.trial_number), 0) AS max_trial",
                    sid=summary.strategy_id,
                ).single()
                next_trial = (result["max_trial"] if result else 0) + 1
                summary_payload = {**summary.model_dump(mode="json"), "trial_number": next_trial}
                tx.run(RUN_STATS_SUMMARY_QUERY, summary=summary_payload).consume()

        session.execute_write(_write)

    def _persist_champion(self, session, payload: dict) -> None:
        metrics = payload["champion"].get("metrics_summary", {})
        # Promote tier out of metrics_summary as a top-level property.
        tier = str(metrics.get("tier", "")).lower() or "pass"
        # Flatten numeric metrics into individual properties for direct Cypher queryability.
        flat_metrics = {
            f"metrics_{k}": v
            for k, v in metrics.items()
            if isinstance(v, (int, float))
        }
        champion_payload = {
            **payload["champion"],
            "tier": tier,
            "metrics_summary_text": json.dumps(
                metrics,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            **flat_metrics,
        }
        pivot_from_run_id = champion_payload.get("pivot_from_run_id")

        def _write(tx) -> None:
            tx.run(
                CHAMPION_INGEST_QUERY,
                champion=champion_payload,
                strategy=payload["strategy"],
                pivot_from_run_id=pivot_from_run_id,
            ).consume()

        session.execute_write(_write)

    def _persist_blob(self, session, payload: dict) -> None:
        def _write(tx) -> None:
            tx.run(
                BLOB_INGEST_QUERY,
                blob=payload["blob"],
                strategy=payload["strategy"],
            ).consume()

        session.execute_write(_write)

    # ---------------------------------------------------------------------------
    # Semantic hypothesis deduplication (QWS-0604)
    # ---------------------------------------------------------------------------

    def set_hypothesis_embedding(
        self,
        hypothesis_id: str,
        embedding: list[float],
    ) -> bool:
        """Store an embedding vector on a Hypothesis node.

        Args:
            hypothesis_id: Target Hypothesis node ID.
            embedding: Float vector from the sentence-transformers model.

        Returns True when found and updated, False when hypothesis not found.

        Raises StoreInfraError on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx) -> list[object]:  # type: ignore[no-untyped-def]
                    result = tx.run(
                        HYPOTHESIS_SET_EMBEDDING_QUERY,
                        hypothesis_id=hypothesis_id,
                        embedding=embedding,
                    )
                    return list(result)

                records = session.execute_write(_write)
                return len(records) > 0
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def get_all_hypothesis_embeddings(self) -> list[dict[str, object]]:
        """Return all Hypothesis nodes that have a stored embedding vector.

        Returns a list of dicts with keys: hypothesis_id, title, embedding.
        Used to avoid recomputing all embeddings on every `qw record --hypothesis` call.

        Raises StoreInfraError on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
                    return [dict(r) for r in tx.run(GET_ALL_HYPOTHESIS_EMBEDDINGS_QUERY)]

                return session.execute_read(_read)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def get_hypotheses_without_embeddings(self) -> list[dict[str, object]]:
        """Return Hypothesis nodes with null embedding (backfill targets).

        Returns a list of dicts with keys: hypothesis_id, title.

        Raises StoreInfraError on Neo4j connectivity or execution failure.
        """
        try:
            with self._driver.session(database=self._database) as session:
                def _read(tx) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
                    return [dict(r) for r in tx.run(GET_HYPOTHESES_WITHOUT_EMBEDDINGS_QUERY)]

                return session.execute_read(_read)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

    def create_semantic_edges(
        self,
        new_hypothesis_id: str,
        new_embedding: list[float],
        existing_embeddings: list[dict[str, object]],
        threshold: float = 0.85,
    ) -> int:
        """Create SEMANTICALLY_RELATED edges for pairs exceeding the cosine similarity threshold.

        The edge is symmetric: A→B and B→A are both created with the same similarity value.
        pair_key is the sorted concatenation of the two IDs joined by pipe (idempotent MERGE key).

        Args:
            new_hypothesis_id: The newly-created Hypothesis node.
            new_embedding: Embedding vector for the new hypothesis.
            existing_embeddings: Output of get_all_hypothesis_embeddings() — excludes new node.
            threshold: Cosine similarity cutoff (default 0.85).

        Returns count of new pairs (each pair = 2 directed edges).

        Raises StoreInfraError on Neo4j connectivity or execution failure.
        """
        import math

        def _cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a * norm_b)

        pairs = []
        for row in existing_embeddings:
            other_id = str(row["hypothesis_id"])
            if other_id == new_hypothesis_id:
                continue
            raw_emb = row["embedding"]
            other_emb: list[float] = [float(v) for v in raw_emb]  # type: ignore[attr-defined]
            sim = _cosine(new_embedding, other_emb)
            if sim >= threshold:
                sorted_ids = sorted([new_hypothesis_id, other_id])
                pairs.append({
                    "hypothesis_id_a": sorted_ids[0],
                    "hypothesis_id_b": sorted_ids[1],
                    "pair_key": f"{sorted_ids[0]}|{sorted_ids[1]}",
                    "similarity": round(sim, 6),
                })

        if not pairs:
            return 0

        try:
            with self._driver.session(database=self._database) as session:
                def _write(tx) -> None:  # type: ignore[no-untyped-def]
                    tx.run(SEMANTICALLY_RELATED_MERGE_QUERY, pairs=pairs).consume()

                session.execute_write(_write)
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

        return len(pairs)

    # ------------------------------------------------------------------
    # FormerChampion lifecycle — QWS-0801
    # ------------------------------------------------------------------

    def degrade_champion(
        self,
        champion_id: str,
        oos_reason: str,
        metrics_sharpe_at_degradation: float | None = None,
    ) -> str:
        """Demote a Champion to FormerChampion.

        Creates a :FormerChampion node and a DEGRADED_TO edge from the Champion.
        The Champion node is NOT deleted — it remains readable.

        Returns:
            former_champion_id — the ID of the newly created FormerChampion node.

        Raises:
            ValueError: if champion_id does not exist or oos_reason is empty.
            StoreInfraError: on Neo4j or unexpected errors.
        """
        if not oos_reason.strip():
            raise ValueError("oos_reason cannot be empty")

        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()
        former_champion_id = _ids.hash12(champion_id, now_iso)

        try:
            with self._driver.session(database=self._database) as session:
                def _check(tx) -> dict | None:  # type: ignore[no-untyped-def]
                    result = tx.run(
                        "MATCH (ch:Champion {champion_id: $cid}) "
                        "RETURN ch.strategy_id AS strategy_id",
                        cid=champion_id,
                    ).single()
                    return dict(result) if result else None

                row = session.execute_read(_check)
                if row is None:
                    raise ValueError(f"Champion not found: {champion_id}")

                strategy_id = row["strategy_id"]

                def _write(tx) -> None:  # type: ignore[no-untyped-def]
                    tx.run(
                        """
                        MATCH (ch:Champion {champion_id: $champion_id})
                        CREATE (fc:FormerChampion {
                            former_champion_id: $former_champion_id,
                            strategy_id:        $strategy_id,
                            champion_id:        $champion_id,
                            degraded_at:        datetime($degraded_at),
                            oos_reason:         $oos_reason
                        })
                        SET fc.metrics_sharpe_at_degradation = $sharpe_at_deg,
                            fc.created_at = datetime()
                        CREATE (ch)-[:DEGRADED_TO {detected_at: datetime($degraded_at)}]->(fc)
                        """,
                        champion_id=champion_id,
                        former_champion_id=former_champion_id,
                        strategy_id=strategy_id,
                        degraded_at=now_iso,
                        oos_reason=oos_reason,
                        sharpe_at_deg=metrics_sharpe_at_degradation,
                    ).consume()

                session.execute_write(_write)
        except ValueError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

        return former_champion_id

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        """Retire a FormerChampion to RetiredChampion.

        Creates a :RetiredChampion node (if one does not already exist) and a
        RETIRED_TO edge from the FormerChampion.  Copies oos_reason from the
        FormerChampion and stores retirement_note on the RetiredChampion.

        Returns:
            retired_champion_id — the ID of the RetiredChampion node.

        Raises:
            ValueError: if former_champion_id does not exist.
            StoreInfraError: on Neo4j or unexpected errors.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()

        try:
            with self._driver.session(database=self._database) as session:
                def _check(tx) -> dict | None:  # type: ignore[no-untyped-def]
                    result = tx.run(
                        "MATCH (fc:FormerChampion {former_champion_id: $fcid}) "
                        "RETURN fc.champion_id AS champion_id, "
                        "       fc.strategy_id AS strategy_id, "
                        "       fc.oos_reason  AS oos_reason",
                        fcid=former_champion_id,
                    ).single()
                    return dict(result) if result else None

                row = session.execute_read(_check)
                if row is None:
                    raise ValueError(f"FormerChampion not found: {former_champion_id}")

                champion_id = row["champion_id"]
                oos_reason = row["oos_reason"]
                retired_champion_id = _ids.hash12(former_champion_id, now_iso)

                def _write(tx) -> None:  # type: ignore[no-untyped-def]
                    tx.run(
                        """
                        MATCH (fc:FormerChampion {former_champion_id: $former_champion_id})
                        MERGE (rc:RetiredChampion {retired_champion_id: $retired_champion_id})
                          ON CREATE SET
                            rc.champion_id       = $champion_id,
                            rc.oos_reason        = $oos_reason,
                            rc.retirement_note   = $retirement_note,
                            rc.retired_at        = datetime($retired_at),
                            rc.created_at        = datetime()
                        CREATE (fc)-[:RETIRED_TO {retired_at: datetime($retired_at)}]->(rc)
                        """,
                        former_champion_id=former_champion_id,
                        retired_champion_id=retired_champion_id,
                        champion_id=champion_id,
                        oos_reason=oos_reason,
                        retirement_note=retirement_note,
                        retired_at=now_iso,
                    ).consume()

                session.execute_write(_write)
        except ValueError:
            raise
        except Neo4jError as exc:
            raise StoreInfraError(f"Neo4j execution failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise StoreInfraError(f"Unexpected store error: {exc}") from exc

        return retired_champion_id


