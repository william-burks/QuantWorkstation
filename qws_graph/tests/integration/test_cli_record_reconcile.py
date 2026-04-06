"""Integration tests for qw record and qw reconcile commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from research.graph.cli import cmd_record, cmd_reconcile
from research.graph.store import StoreResult


@pytest.fixture
def temp_repo_root() -> Path:
    """Temporary directory for test artifacts and .qws structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def csv_baseline(temp_repo_root: Path) -> Path:
    """Create a minimal baseline CSV for testing."""
    results_dir = temp_repo_root / "results"
    results_dir.mkdir(parents=True)
    csv_file = results_dir / "test_baseline.csv"
    csv_file.write_text(
        "instrument,timeframe,direction,logic_type,timestamp,sharpe,profit_factor,win_rate,max_drawdown,total_trades,total_r\n"
        "ES,1H,bear,baseline,2026-04-02T12:30:00Z,1.3749,1.1562,0.3737,-8.686,99,10.1601\n"
    )
    return csv_file


class TestRecordCommand:
    """Tests for qw record command."""

    def test_record_csv_baseline_dry_run(self, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Test record with --dry-run on valid CSV."""
        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.bundle = None
        args.kind = "baseline_csv"
        args.pivot_from = None
        args.offline = False
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = True

        exit_code = cmd_record(args)
        assert exit_code == 0

    def test_record_csv_baseline_offline(self, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Test record with --offline writes to pending queue."""
        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.bundle = None
        args.kind = "baseline_csv"
        args.pivot_from = None
        args.offline = True
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 0

        # Verify pending file was created
        pending_dir = temp_repo_root / ".qws" / "pending"
        assert pending_dir.exists()
        pending_files = list(pending_dir.glob("*.json"))
        assert len(pending_files) > 0

        # Verify receipt was created
        receipts_dir = temp_repo_root / ".qws" / "receipts"
        assert receipts_dir.exists()
        receipt_files = list(receipts_dir.glob("*.json"))
        assert len(receipt_files) > 0

        # Verify receipt status is pending_offline
        receipt_path = receipt_files[0]
        receipt = json.loads(receipt_path.read_text())
        assert receipt["status"] == "pending_offline"

    def test_record_csv_missing_file(self, temp_repo_root: Path) -> None:
        """Test record with missing file returns exit code 1."""
        args = mock.MagicMock()
        args.file = str(temp_repo_root / "missing.csv")
        args.kind = "baseline_csv"
        args.pivot_from = None
        args.offline = True
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 1

    def test_record_csv_invalid_kind(self, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Test record with invalid artifact kind returns exit code 1."""
        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.kind = "invalid_kind"
        args.pivot_from = None
        args.offline = True
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 1

    @mock.patch("research.graph.cli.NeoConnector.is_available")
    def test_record_online_neo_unavailable(
        self, mock_is_available, csv_baseline: Path, temp_repo_root: Path
    ) -> None:
        """Test record without --offline when Neo4j is down returns exit code 2."""
        mock_is_available.return_value = False

        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.bundle = None
        args.kind = "baseline_csv"
        args.pivot_from = None
        args.offline = False
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 2

        # No pending or receipt files should be created
        pending_dir = temp_repo_root / ".qws" / "pending"
        receipts_dir = temp_repo_root / ".qws" / "receipts"
        if pending_dir.exists():
            assert len(list(pending_dir.glob("*.json"))) == 0
        if receipts_dir.exists():
            assert len(list(receipts_dir.glob("*.json"))) == 0

    @mock.patch("research.graph.cli.GraphStore.from_env")
    @mock.patch("research.graph.cli.NeoConnector.is_available")
    def test_record_online_calls_store_for_csv(self, mock_is_available, mock_store_factory, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Online CSV ingest calls GraphStore.persist_artifact and writes persisted receipt."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
        )
        mock_store_factory.return_value = mock_store

        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.bundle = None
        args.kind = "baseline_csv"
        args.pivot_from = None
        args.offline = False
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 0
        assert mock_store.persist_artifact.call_count == 1

    @mock.patch("research.graph.cli.GraphStore.from_env")
    @mock.patch("research.graph.cli.NeoConnector.is_available")
    def test_record_online_calls_store_for_champion(self, mock_is_available, mock_store_factory, temp_repo_root: Path) -> None:
        """Online champion ingest calls GraphStore.persist_artifact."""
        champion = Path("/Users/will/ClaudeProjects/QuantWorkstation/qws_graph/tests/fixtures/artifacts/champion/es_bear_sweep_1h_v1.md")
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Champion": 1},
            relationship_counts={"PRODUCED_CHAMPION": 1, "PIVOTED_FROM": 1},
        )
        mock_store_factory.return_value = mock_store

        args = mock.MagicMock()
        args.file = str(champion)
        args.bundle = None
        args.kind = "champion_md"
        args.pivot_from = None
        args.offline = False
        args.timeout_seconds = 3
        args.repo_root = "/Users/will/ClaudeProjects/QuantWorkstation/qws_graph"
        args.dry_run = False

        exit_code = cmd_record(args)
        assert exit_code == 0
        assert mock_store.persist_artifact.call_count == 1


class TestReconcileCommand:
    """Tests for qw reconcile command."""

    def test_reconcile_empty(self, temp_repo_root: Path) -> None:
        """Test reconcile on empty repo."""
        args = mock.MagicMock()
        args.repo_root = str(temp_repo_root)
        args.since = None
        args.json = False

        exit_code = cmd_reconcile(args)
        assert exit_code == 0

    def test_reconcile_with_pending(self, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Test reconcile reports pending files."""
        # Create a pending file
        pending_dir = temp_repo_root / ".qws" / "pending"
        pending_dir.mkdir(parents=True)
        pending_file = pending_dir / "test_artifact_id.json"
        pending_file.write_text(json.dumps({"kind": "baseline_csv"}))

        args = mock.MagicMock()
        args.repo_root = str(temp_repo_root)
        args.since = None
        args.json = False

        exit_code = cmd_reconcile(args)
        assert exit_code == 0

    def test_reconcile_json_output(self, temp_repo_root: Path) -> None:
        """Test reconcile --json produces valid JSON."""
        args = mock.MagicMock()
        args.repo_root = str(temp_repo_root)
        args.since = None
        args.json = True

        # Capture stdout
        import io
        import sys

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured_output
            exit_code = cmd_reconcile(args)
            sys.stdout = old_stdout
        except Exception:
            sys.stdout = old_stdout
            raise

        assert exit_code == 0
        output = captured_output.getvalue()
        # Should be valid JSON
        result = json.loads(output)
        assert "missing_in_graph" in result


