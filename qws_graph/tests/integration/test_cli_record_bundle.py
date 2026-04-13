# mypy: ignore-errors
"""Integration tests for QWS-0904: phantom champion ID fix.

AC: auto-promoted champion printed ID equals the ID returned by get_recent_champions_v1
    for the same strategy.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from research.graph.store import EvolutionOutcome, StoreInfraError, StoreResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bundle_dir(
    temp_dir: Path,
    sharpe: float = 2.5,
    total_trades: int = 50,
) -> Path:
    """Create a minimal bundle directory with one baseline CSV row."""
    bundle_dir = temp_dir / "bundle"
    bundle_dir.mkdir(parents=True)

    csv_file = bundle_dir / "results.csv"
    csv_file.write_text(
        "instrument,timeframe,direction,logic_type,timestamp,sharpe,profit_factor,"
        "win_rate,max_drawdown,total_trades,total_r,first_trade_ts,last_trade_ts\n"
        f"MES,1H,bear,test_0904,2026-04-12T00:00:00Z,{sharpe},1.50,0.55,-0.08,"
        f"{total_trades},12.0,2024-01-01T00:00:00Z,2026-04-01T00:00:00Z\n"
    )

    manifest: dict = {"files": {"csv": "results.csv", "csv_kind": "baseline_csv"}}
    (bundle_dir / "bundle.json").write_text(json.dumps(manifest))
    return bundle_dir


def _make_args(bundle_dir: Path, temp_dir: Path) -> mock.MagicMock:
    args = mock.MagicMock()
    args.bundle = str(bundle_dir)
    args.file = None
    args.hypothesis = None
    args.oos = None
    args.offline = False
    args.dry_run = False
    args.timeout_seconds = 3
    args.repo_root = str(temp_dir)
    args.source_file = None
    args.regime = None
    args.rationale = None
    return args


# ---------------------------------------------------------------------------
# Mock-based tests (no live Neo4j required)
# ---------------------------------------------------------------------------


@mock.patch("research.graph.cli.GraphStore.from_env")
@mock.patch("research.graph.cli.NeoConnector.is_available")
class TestPhantomChampionIdFix:
    """AC: printed champion_id equals persisted graph champion_id (no phantom IDs)."""

    def test_auto_promoted_id_printed_matches_store_return(
        self, mock_is_available, mock_store_factory, capsys
    ) -> None:
        """Printed champion_id comes from store.persist_artifact return value, not pre-write hash."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()

        verified_champion_id = "b2a6d9624968"  # simulates graph-persisted ID
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
            evolution=[
                EvolutionOutcome(
                    run_id="abc123def456",
                    status="promoted",
                    reason="",
                    evidence_score=17.7,
                    champion_id=verified_champion_id,
                )
            ],
        )
        mock_store_factory.return_value = mock_store

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = _make_bundle_dir(Path(tmpdir))
            args = _make_args(bundle_dir, Path(tmpdir))

            from research.graph.cli import cmd_record

            exit_code = cmd_record(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # The printed ID must be the one from store return, not any other value
        assert verified_champion_id in captured.out

    def test_write_fail_exits_nonzero_no_ok(
        self, mock_is_available, mock_store_factory, capsys
    ) -> None:
        """AC4: if Neo4j write fails, command exits non-zero with ERROR, no OK printed."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.side_effect = StoreInfraError("Neo4j write failed: tx aborted")
        mock_store_factory.return_value = mock_store

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = _make_bundle_dir(Path(tmpdir))
            args = _make_args(bundle_dir, Path(tmpdir))

            from research.graph.cli import cmd_record

            exit_code = cmd_record(args)

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "OK" not in captured.out
        assert "ERROR" in captured.err

    def test_readback_failure_exits_nonzero_no_ok(
        self, mock_is_available, mock_store_factory, capsys
    ) -> None:
        """AC3: write succeeds but read-back finds no node — exits non-zero, no OK printed.

        Simulated by having persist_artifact raise StoreInfraError (the store raises this
        when read-back returns no node after a successful write).
        """
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.side_effect = StoreInfraError(
            "Champion promoted but read-back found no node: strategy=mes-1h-bear-test0904"
        )
        mock_store_factory.return_value = mock_store

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = _make_bundle_dir(Path(tmpdir))
            args = _make_args(bundle_dir, Path(tmpdir))

            from research.graph.cli import cmd_record

            exit_code = cmd_record(args)

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "OK" not in captured.out
        assert "ERROR" in captured.err

    def test_no_promotion_no_champion_id_in_output(
        self, mock_is_available, mock_store_factory, capsys
    ) -> None:
        """When no auto-promotion occurs, no champion ID is printed."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
            evolution=[
                EvolutionOutcome(
                    run_id="abc123def456",
                    status="recorded",
                    reason="",
                    evidence_score=5.0,
                    champion_id=None,
                )
            ],
        )
        mock_store_factory.return_value = mock_store

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = _make_bundle_dir(Path(tmpdir))
            args = _make_args(bundle_dir, Path(tmpdir))

            from research.graph.cli import cmd_record

            exit_code = cmd_record(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Champion" not in captured.out or "→ Champion" not in captured.out


# ---------------------------------------------------------------------------
# Live Neo4j tests
# ---------------------------------------------------------------------------


def _require_live_neo4j() -> tuple[str, str, str]:
    from neo4j import GraphDatabase

    uri, user, password = "bolt://127.0.0.1:7687", "neo4j", "password"
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=2)
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")
    finally:
        driver.close()
    return uri, user, password


class TestPhantomIdE2E:
    """E2E: auto-promoted champion printed ID == graph ID for same strategy.

    Requires live Neo4j — skipped when unavailable.
    """

    @pytest.fixture(autouse=True)
    def clean_graph(self):
        uri, user, password = _require_live_neo4j()
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
        try:
            with driver.session(database="neo4j") as session:
                session.run("MATCH (n) DETACH DELETE n").consume()
        finally:
            driver.close()

    def test_printed_champion_id_matches_graph_id(self) -> None:
        """After bundle ingest with auto-promotion, printed ID == ID in Neo4j."""
        from research.graph.query import GraphQueryService
        from research.graph.store import GraphStore

        uri, user, password = _require_live_neo4j()
        store = GraphStore(uri=uri, username=user, password=password, timeout_seconds=3)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                bundle_dir = _make_bundle_dir(Path(tmpdir), sharpe=2.5, total_trades=50)
                csv_path = bundle_dir / "results.csv"

                from research.graph.parsers import CSVParser

                artifact, _ = CSVParser(csv_path, kind="baseline_csv").parse()
                result = store.persist_artifact(artifact, promotion_rationale="")

            # Find the promoted outcome
            promoted = [o for o in result.evolution if o.status == "promoted"]
            assert len(promoted) == 1, "Expected exactly one promoted run"
            printed_champion_id = promoted[0].champion_id
            assert printed_champion_id is not None, "champion_id must not be None after promotion"

            # Query graph for champion of this strategy
            with store._driver.session(database=store._database) as session:
                row = session.run(
                    """
                    MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
                    WHERE s.strategy_id = $sid
                    RETURN ch.champion_id AS champion_id
                    """,
                    sid=artifact.strategy.strategy_id,
                ).single()

            assert row is not None, "Champion node not found in graph after promotion"
            graph_champion_id = str(row["champion_id"])

            # The core assertion: printed ID == graph ID
            assert printed_champion_id == graph_champion_id, (
                f"Phantom ID detected: printed={printed_champion_id!r} "
                f"but graph has {graph_champion_id!r}"
            )
        finally:
            store.close()
