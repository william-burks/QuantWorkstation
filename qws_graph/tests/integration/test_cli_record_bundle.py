# mypy: ignore-errors
"""Integration test: auto-promoted champion printed ID == graph ID (QWS-0904)."""

from __future__ import annotations

import json
import sys
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from research.graph.cli import cmd_record
from research.graph.store import GraphStore

_BOLT_URI = "bolt://127.0.0.1:7687"
_USER = "neo4j"
_PASSWORD = "password"

# CSV with Sharpe 4.80 — qualifies for auto-promotion
_QUALIFYING_CSV = (
    "target_r,max_hold_bars,wick_mode,chain_mode,sample_size,total_r,avg_r_per_trade,"
    "breakeven_win_rate,sharpe,profit_factor,win_rate,total_trades,return,max_drawdown,"
    "calmar,gain,fees,first_trade_ts,last_trade_ts,backtest_start,backtest_end,"
    "tier,beat_bh,fee_pct_of_gain,instrument,timeframe,direction,logic_type\n"
    "1.25,24,exclude_q2,no_smt_in_chain,32,8.3,0.259,0.444444,4.80,1.79,0.3125,32,"
    "0.081,-0.027,23.9,,,2025-01-15T18:50:00-05:00,2026-03-12T19:15:00-04:00,"
    "2023-12-25T18:00:00-05:00,2026-03-20T16:00:00-04:00,professional,True,,CL,1H,bear,liquidity-sweep\n"
)


def _require_live_neo4j() -> None:
    driver = GraphDatabase.driver(_BOLT_URI, auth=(_USER, _PASSWORD), connection_timeout=2)
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")
    finally:
        driver.close()


def _clean_graph() -> None:
    driver = GraphDatabase.driver(_BOLT_URI, auth=(_USER, _PASSWORD), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _get_champion_id_for_strategy(strategy_id: str) -> str | None:
    """Query Neo4j for the active Champion ID for the given strategy_id."""
    driver = GraphDatabase.driver(_BOLT_URI, auth=(_USER, _PASSWORD), connection_timeout=3)
    try:
        with driver.session(database="neo4j") as session:
            result = session.run(
                """
                MATCH (s:Strategy {strategy_id: $sid})-[:PRODUCED_CHAMPION]->(ch:Champion)
                RETURN ch.champion_id AS champion_id
                ORDER BY ch.freeze_date DESC LIMIT 1
                """,
                sid=strategy_id,
            ).single()
            return result["champion_id"] if result else None
    finally:
        driver.close()


@pytest.fixture(autouse=True)
def clean_graph() -> None:
    _require_live_neo4j()
    _clean_graph()
    yield
    _clean_graph()


class TestAutopromoteChampionIdVerified:
    """Printed champion ID must equal graph champion ID after auto-promotion (QWS-0904)."""

    def test_printed_champion_id_matches_graph_id(self) -> None:
        """Auto-promotion: printed ID == PRODUCED_CHAMPION.champion_id in Neo4j."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "test_bundle"
            bundle_dir.mkdir()

            csv_path = bundle_dir / "results.csv"
            csv_path.write_text(_QUALIFYING_CSV)

            manifest = {
                "files": {"csv": "results.csv", "csv_kind": "sweep_csv"},
            }
            (bundle_dir / "bundle.json").write_text(json.dumps(manifest))

            from unittest import mock

            args = mock.MagicMock()
            args.bundle = str(bundle_dir)
            args.file = None
            args.hypothesis = None
            args.oos = None
            args.regime = None
            args.offline = False
            args.dry_run = False
            args.timeout_seconds = 5
            args.repo_root = str(Path(tmpdir))
            args.rationale = None
            args.source_file = None

            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                exit_code = cmd_record(args)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()
            assert exit_code == 0, f"cmd_record returned {exit_code}; output:\n{output}"

            # Extract printed champion ID from output line like:
            #   [PROMOTED] <run_id> → Champion <champion_id>
            printed_id: str | None = None
            for line in output.splitlines():
                if "[PROMOTED]" in line and "Champion" in line:
                    # e.g. "  [PROMOTED] abc123 ev=4.80 → Champion d1aa95c91f26"
                    parts = line.split("Champion")
                    if len(parts) >= 2:
                        printed_id = parts[-1].strip()
                        break

            assert printed_id is not None, (
                f"No [PROMOTED] champion line found in output:\n{output}"
            )

            # Derive strategy_id from the fixture (CL, 1H, bear, liquidity-sweep)
            # strategy_id is computed deterministically — query by strategy properties
            graph_store = GraphStore(
                uri=_BOLT_URI,
                username=_USER,
                password=_PASSWORD,
                timeout_seconds=5,
            )
            try:
                # Find strategy_id for the promoted champion
                driver = GraphDatabase.driver(
                    _BOLT_URI, auth=(_USER, _PASSWORD), connection_timeout=3
                )
                try:
                    with driver.session(database="neo4j") as session:
                        result = session.run(
                            """
                            MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
                            RETURN ch.champion_id AS champion_id, s.strategy_id AS strategy_id
                            LIMIT 1
                            """
                        ).single()
                        assert result is not None, "No Champion node found in graph after promotion"
                        graph_id = result["champion_id"]
                        strategy_id = result["strategy_id"]
                finally:
                    driver.close()
            finally:
                graph_store.close()

            assert printed_id == graph_id, (
                f"Phantom ID bug: printed='{printed_id}' graph='{graph_id}' "
                f"strategy='{strategy_id}'"
            )

    def test_bundle_dry_run_no_champion_write(self) -> None:
        """Dry run must not write any Champion node."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "dry_bundle"
            bundle_dir.mkdir()

            csv_path = bundle_dir / "results.csv"
            csv_path.write_text(_QUALIFYING_CSV)

            manifest = {"files": {"csv": "results.csv", "csv_kind": "sweep_csv"}}
            (bundle_dir / "bundle.json").write_text(json.dumps(manifest))

            from unittest import mock

            args = mock.MagicMock()
            args.bundle = str(bundle_dir)
            args.file = None
            args.hypothesis = None
            args.oos = None
            args.regime = None
            args.offline = False
            args.dry_run = True
            args.timeout_seconds = 5
            args.repo_root = str(Path(tmpdir))
            args.rationale = None
            args.source_file = None

            exit_code = cmd_record(args)
            assert exit_code == 0

            # No Champion written
            graph_id = _get_champion_id_for_strategy("any")
            assert graph_id is None
