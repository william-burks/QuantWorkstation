"""Integration tests for the Neo4j idempotent store layer."""

from __future__ import annotations

from pathlib import Path

import pytest
from neo4j import GraphDatabase
from research.graph.parsers import ChampionMarkdownParser, CSVParser
from research.graph.store import GraphStore, StoreInfraError

REPO_ROOT = Path("/Users/will/ClaudeProjects/QuantWorkstation/qws_graph")
_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "artifacts"
BASELINE_FIXTURE = _FIXTURES / "baseline" / "es_bear_baseline_fixture.txt"
CHAMPION_FIXTURE = _FIXTURES / "champion" / "es_bear_sweep_1h_v1.md"


def _neo4j_params() -> tuple[str, str, str]:
    # Keep defaults aligned with env.example and Story 0 defaults.
    uri = "bolt://127.0.0.1:7687"
    user = "neo4j"
    password = "password"
    return uri, user, password


def _require_live_neo4j() -> tuple[str, str, str]:
    uri, user, password = _neo4j_params()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=2)
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available for store integration tests: {exc}")
    finally:
        driver.close()
    return uri, user, password


@pytest.fixture
def graph_store() -> GraphStore:
    uri, user, password = _require_live_neo4j()
    store = GraphStore(uri=uri, username=user, password=password, timeout_seconds=3)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture(autouse=True)
def clean_graph() -> None:
    uri, user, password = _require_live_neo4j()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _count_graph() -> dict[str, int]:
    uri, user, password = _neo4j_params()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            strategy = session.run("MATCH (:Strategy) RETURN count(*) AS c").single()["c"]
            run_count = session.run("MATCH (:Run) RETURN count(*) AS c").single()["c"]
            config = session.run("MATCH (:Config) RETURN count(*) AS c").single()["c"]
            champion = session.run("MATCH (:Champion) RETURN count(*) AS c").single()["c"]
            blob = session.run("MATCH (:BlobArtifact) RETURN count(*) AS c").single()["c"]
            has_run = session.run(
                "MATCH (:Strategy)-[r:HAS_RUN]->(:Run) RETURN count(r) AS c"
            ).single()["c"]
            uses_config = session.run(
                "MATCH (:Run)-[r:USES_CONFIG]->(:Config) RETURN count(r) AS c"
            ).single()["c"]
            produced = session.run(
                "MATCH (:Strategy)-[r:PRODUCED_CHAMPION]->(:Champion) RETURN count(r) AS c"
            ).single()["c"]
            pivoted = session.run(
                "MATCH (:Champion)-[r:PIVOTED_FROM]->(:Run) RETURN count(r) AS c"
            ).single()["c"]
            return {
                "Strategy": strategy,
                "Run": run_count,
                "Config": config,
                "Champion": champion,
                "BlobArtifact": blob,
                "HAS_RUN": has_run,
                "USES_CONFIG": uses_config,
                "PRODUCED_CHAMPION": produced,
                "PIVOTED_FROM": pivoted,
            }
    finally:
        driver.close()


def test_double_ingesting_same_csv_no_extra_nodes_or_relationships(graph_store: GraphStore) -> None:
    artifact, _warnings = CSVParser(BASELINE_FIXTURE, kind="baseline_csv").parse()

    graph_store.persist_artifact(artifact)
    after_first = _count_graph()

    graph_store.persist_artifact(artifact)
    after_second = _count_graph()

    assert after_second == after_first


def test_champion_ingest_creates_produced_and_optional_pivoted_from(
    graph_store: GraphStore,
) -> None:
    artifact, _warnings = ChampionMarkdownParser(CHAMPION_FIXTURE).parse()

    graph_store.persist_artifact(artifact)
    counts = _count_graph()

    assert counts["Champion"] == 1
    assert counts["PRODUCED_CHAMPION"] == 1
    assert counts["PIVOTED_FROM"] == 1


def test_store_returns_counts_and_status_for_receipts(graph_store: GraphStore) -> None:
    artifact, _warnings = CSVParser(BASELINE_FIXTURE, kind="baseline_csv").parse()

    result = graph_store.persist_artifact(artifact)

    assert result.status == "persisted"
    assert result.node_counts["Strategy"] == 1
    assert result.node_counts["Run"] == len(artifact.runs)
    assert result.relationship_counts["HAS_RUN"] == len(artifact.runs)


def test_infra_errors_propagate_as_store_layer_exceptions() -> None:
    artifact, _warnings = CSVParser(BASELINE_FIXTURE, kind="baseline_csv").parse()
    # Port 1 should reliably fail fast on localhost.
    broken = GraphStore(
        uri="bolt://127.0.0.1:1", username="neo4j", password="password", timeout_seconds=1
    )

    try:
        with pytest.raises(StoreInfraError):
            broken.persist_artifact(artifact)
    finally:
        broken.close()
