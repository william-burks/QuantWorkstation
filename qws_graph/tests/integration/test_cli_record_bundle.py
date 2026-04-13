# mypy: ignore-errors
"""Integration tests for qw record --bundle auto-promotion champion ID integrity.

QWS-0904: verify that the champion ID printed by _cmd_bundle after auto-promotion
equals the ID persisted in Neo4j (read-after-write correctness).
"""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from neo4j import GraphDatabase
from research.graph.cli import cmd_record
from research.graph.store import GraphStore

_REPO_ROOT = Path("/Users/will/ClaudeProjects/QuantWorkstation/qws_graph")
_QUALIFYING_CSV = (
    _REPO_ROOT
    / "tests"
    / "fixtures"
    / "artifacts"
    / "baseline"
    / "promotion_alert_qualifying.csv"
)


def _neo4j_params() -> tuple[str, str, str]:
    return "bolt://127.0.0.1:7687", "neo4j", "password"


def _require_live_neo4j() -> tuple[str, str, str]:
    uri, user, password = _neo4j_params()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=2)
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")
    finally:
        driver.close()
    return uri, user, password


@pytest.fixture(autouse=True)
def _clean_graph() -> None:
    uri, user, password = _require_live_neo4j()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _get_champion_id_from_graph(strategy_id: str) -> str | None:
    """Query Neo4j for the active Champion node for a strategy. Returns champion_id or None."""
    uri, user, password = _neo4j_params()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            row = session.run(
                "MATCH (s:Strategy {strategy_id: $sid})-[:PRODUCED_CHAMPION]->(ch:Champion) "
                "RETURN ch.champion_id AS champion_id",
                sid=strategy_id,
            ).single()
            return row["champion_id"] if row else None
    finally:
        driver.close()


def _get_strategy_id_from_graph() -> str | None:
    """Return the first Strategy node's strategy_id (assumes clean graph with single strategy)."""
    uri, user, password = _neo4j_params()
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            row = session.run("MATCH (s:Strategy) RETURN s.strategy_id AS sid LIMIT 1").single()
            return row["sid"] if row else None
    finally:
        driver.close()


class TestBundleChampionIdIntegrity:
    """QWS-0904: printed champion ID must equal the persisted graph ID."""

    def _make_bundle(self, tmpdir: Path) -> Path:
        """Create a minimal bundle directory with qualifying CSV and bundle.json."""
        bundle_dir = tmpdir / "test_bundle"
        bundle_dir.mkdir(parents=True)

        csv_dest = bundle_dir / "results.csv"
        csv_dest.write_text(_QUALIFYING_CSV.read_text(encoding="utf-8"), encoding="utf-8")

        manifest = {
            "files": {
                "csv": "results.csv",
                "csv_kind": "baseline_csv",
            }
        }
        (bundle_dir / "bundle.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return bundle_dir

    def _make_args(self, bundle_dir: Path, tmpdir: Path) -> mock.MagicMock:
        args = mock.MagicMock()
        args.bundle = str(bundle_dir)
        args.file = None
        args.hypothesis = None
        args.oos = None
        args.regime = None
        args.kind = None
        args.pivot_from = None
        args.offline = False
        args.timeout_seconds = 5
        args.repo_root = str(tmpdir)
        args.dry_run = False
        args.rationale = None
        args.source_file = None
        return args

    def test_printed_champion_id_matches_graph_id(self, capsys) -> None:
        """Auto-promoted champion: printed ID == graph ID (read-after-write)."""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            bundle_dir = self._make_bundle(tmpdir)
            args = self._make_args(bundle_dir, tmpdir)

            exit_code = cmd_record(args)
            assert exit_code == 0, f"cmd_record exited with {exit_code}"

            captured = capsys.readouterr()
            stdout = captured.out

            # Extract printed champion ID from "[PROMOTED] <run_id> ev=N.NN → Champion <id>"
            printed_champion_id: str | None = None
            for line in stdout.splitlines():
                if "[PROMOTED]" in line and "Champion" in line:
                    parts = line.split("Champion")
                    if len(parts) >= 2:
                        printed_champion_id = parts[-1].strip()
                        break

            assert printed_champion_id is not None, (
                f"No [PROMOTED] line with Champion ID found in output:\n{stdout}"
            )

            # Get strategy_id from graph, then get champion_id
            strategy_id = _get_strategy_id_from_graph()
            assert strategy_id is not None, "No Strategy node found in graph after bundle ingest"

            graph_champion_id = _get_champion_id_from_graph(strategy_id)
            assert graph_champion_id is not None, (
                f"No active Champion found in graph for strategy {strategy_id}"
            )

            assert printed_champion_id == graph_champion_id, (
                f"Phantom ID bug: printed={printed_champion_id!r} "
                f"graph={graph_champion_id!r} — they must match"
            )
