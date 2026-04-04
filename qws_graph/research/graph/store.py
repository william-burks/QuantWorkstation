"""Neo4j store layer for idempotent Graph V1 writes."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from .cypher import BLOB_INGEST_QUERY, CHAMPION_INGEST_QUERY, CSV_INGEST_QUERY
from .models import ResearchArtifact


class StoreError(RuntimeError):
    """Base store exception."""


class StoreInfraError(StoreError):
    """Raised when Neo4j connectivity or execution fails."""


@dataclass(frozen=True)
class StoreResult:
    """Store write result used for receipts and CLI output."""

    status: str
    node_counts: dict[str, int]
    relationship_counts: dict[str, int]


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

    def persist_artifact(self, artifact: ResearchArtifact) -> StoreResult:
        payload = artifact.model_dump(mode="json")

        try:
            with self._driver.session(database=self._database) as session:
                if artifact.kind in {"baseline_csv", "grid_csv"}:
                    self._persist_csv(session, payload)
                    return StoreResult(
                        status="persisted",
                        node_counts={
                            "Strategy": 1,
                            "Run": len(artifact.runs),
                            "Config": len(artifact.configs),
                        },
                        relationship_counts={
                            "HAS_RUN": len(artifact.runs),
                            "USES_CONFIG": len(artifact.runs),
                        },
                    )

                if artifact.kind == "champion_md":
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

    def _persist_csv(self, session, payload: dict) -> None:
        rows = []
        strategy_payload = payload["strategy"]
        for run_payload, config_payload in zip(payload["runs"], payload["configs"], strict=True):
            config_for_query = {
                **config_payload,
                "params_json_text": json.dumps(config_payload.get("params_json", {}), sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                "risk_params_text": json.dumps(config_payload.get("risk_params", {}), sort_keys=True, separators=(",", ":"), ensure_ascii=True),
            }
            rows.append(
                {
                    "strategy": strategy_payload,
                    "run": run_payload,
                    "config": config_for_query,
                }
            )

        def _write(tx) -> None:
            tx.run(CSV_INGEST_QUERY, rows=rows).consume()

        session.execute_write(_write)

    def _persist_champion(self, session, payload: dict) -> None:
        champion_payload = {
            **payload["champion"],
            "metrics_summary_text": json.dumps(
                payload["champion"].get("metrics_summary", {}),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
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


