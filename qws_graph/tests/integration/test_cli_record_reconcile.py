# mypy: ignore-errors
"""Integration tests for qw record and qw reconcile commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from research.graph.cli import cmd_reconcile, cmd_record
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
        "instrument,timeframe,direction,logic_type,timestamp,sharpe,profit_factor,win_rate,max_drawdown,total_trades,total_r,first_trade_ts,last_trade_ts\n"
        "ES,1H,bear,baseline,2026-04-02T12:30:00Z,1.3749,1.1562,0.3737,-8.686,99,10.1601,2024-01-01T00:00:00Z,2026-04-01T00:00:00Z\n"
    )
    return csv_file


class TestRecordCommand:
    """Tests for qw record command."""

    def test_record_csv_baseline_dry_run(self, csv_baseline: Path, temp_repo_root: Path) -> None:
        """Test record with --dry-run on valid CSV."""
        args = mock.MagicMock()
        args.file = str(csv_baseline)
        args.bundle = None
        args.hypothesis = None
        args.oos = None
        args.regime = None
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
        args.hypothesis = None
        args.oos = None
        args.regime = None
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
        args.bundle = None
        args.hypothesis = None
        args.oos = None
        args.regime = None
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
        args.bundle = None
        args.hypothesis = None
        args.oos = None
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
        args.hypothesis = None
        args.oos = None
        args.regime = None
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
    def test_record_online_calls_store_for_csv(
        self, mock_is_available, mock_store_factory, csv_baseline: Path, temp_repo_root: Path
    ) -> None:
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
        args.hypothesis = None
        args.oos = None
        args.regime = None
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
    def test_record_online_calls_store_for_champion(
        self, mock_is_available, mock_store_factory, temp_repo_root: Path
    ) -> None:
        """Online champion ingest calls GraphStore.persist_artifact."""
        champion = Path(
            "/Users/will/ClaudeProjects/QuantWorkstation/qws_graph"
            "/tests/fixtures/artifacts/champion/es_bear_sweep_1h_v1.md"
        )
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
        args.hypothesis = None
        args.oos = None
        args.regime = None
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


@mock.patch("research.graph.cli.GraphStore.from_env")
@mock.patch("research.graph.cli.NeoConnector.is_available")
class TestBundleHypothesisAutolink:
    """E2E tests for QWS-HF-001 Fix 1: bundle hypothesis_id → TESTED_AS edge."""

    def _make_bundle_dir(self, temp_repo_root: Path, hypothesis_id: str | None = None) -> Path:
        """Create a minimal bundle directory with bundle.json and a baseline CSV."""
        bundle_dir = temp_repo_root / "bundle"
        bundle_dir.mkdir(parents=True)

        csv_file = bundle_dir / "results.csv"
        csv_file.write_text(
            "instrument,timeframe,direction,logic_type,timestamp,sharpe,profit_factor,"
            "win_rate,max_drawdown,total_trades,total_r,first_trade_ts,last_trade_ts\n"
            "ES,1H,bear,baseline,2026-04-02T12:30:00Z,1.3749,1.1562,0.3737,-8.686,99,"
            "10.1601,2024-01-01T00:00:00Z,2026-04-01T00:00:00Z\n"
        )

        manifest: dict = {
            "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        }
        if hypothesis_id is not None:
            manifest["hypothesis_id"] = hypothesis_id

        (bundle_dir / "bundle.json").write_text(json.dumps(manifest))
        return bundle_dir

    def _make_args(self, bundle_dir: Path, temp_repo_root: Path) -> mock.MagicMock:
        args = mock.MagicMock()
        args.bundle = str(bundle_dir)
        args.file = None
        args.hypothesis = None
        args.oos = None
        args.offline = False
        args.dry_run = False
        args.timeout_seconds = 3
        args.repo_root = str(temp_repo_root)
        args.source_file = None
        args.regime = None
        args.rationale = None
        return args

    def test_bundle_with_hypothesis_id_calls_link(
        self, mock_is_available, mock_store_factory, temp_repo_root: Path
    ) -> None:
        """bundle.json with hypothesis_id triggers link_hypothesis_tested_as after ingest."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
        )
        mock_store.link_hypothesis_tested_as.return_value = True
        mock_store_factory.return_value = mock_store

        hyp_id = "a0e7380e58e8"
        bundle_dir = self._make_bundle_dir(temp_repo_root, hypothesis_id=hyp_id)
        args = self._make_args(bundle_dir, temp_repo_root)

        exit_code = cmd_record(args)

        assert exit_code == 0
        assert mock_store.link_hypothesis_tested_as.call_count == 1
        call_args = mock_store.link_hypothesis_tested_as.call_args
        assert call_args[0][0] == hyp_id  # hypothesis_id passed

    def test_bundle_without_hypothesis_id_skips_link(
        self, mock_is_available, mock_store_factory, temp_repo_root: Path
    ) -> None:
        """bundle.json without hypothesis_id does not call link_hypothesis_tested_as."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
        )
        mock_store_factory.return_value = mock_store

        bundle_dir = self._make_bundle_dir(temp_repo_root, hypothesis_id=None)
        args = self._make_args(bundle_dir, temp_repo_root)

        exit_code = cmd_record(args)

        assert exit_code == 0
        mock_store.link_hypothesis_tested_as.assert_not_called()

    def test_bundle_hypothesis_not_in_graph_prints_warning(
        self, mock_is_available, mock_store_factory, temp_repo_root: Path, capsys
    ) -> None:
        """When hypothesis not found (link returns False), ingest still succeeds with WARNING."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.persist_artifact.return_value = StoreResult(
            status="persisted",
            node_counts={"Strategy": 1, "Run": 1, "Config": 1},
            relationship_counts={"HAS_RUN": 1, "USES_CONFIG": 1},
        )
        mock_store.link_hypothesis_tested_as.return_value = False
        mock_store_factory.return_value = mock_store

        hyp_id = "a0e7380e58e8"
        bundle_dir = self._make_bundle_dir(temp_repo_root, hypothesis_id=hyp_id)
        args = self._make_args(bundle_dir, temp_repo_root)

        exit_code = cmd_record(args)

        assert exit_code == 0  # ingest still succeeds
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert hyp_id in captured.err

    def test_bundle_dry_run_skips_hypothesis_link(
        self, mock_is_available, mock_store_factory, temp_repo_root: Path
    ) -> None:
        """Dry-run mode exits before ingest — TESTED_AS edge must not be created."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store_factory.return_value = mock_store

        hyp_id = "a0e7380e58e8"
        bundle_dir = self._make_bundle_dir(temp_repo_root, hypothesis_id=hyp_id)
        args = self._make_args(bundle_dir, temp_repo_root)
        args.dry_run = True

        exit_code = cmd_record(args)

        assert exit_code == 0
        mock_store.link_hypothesis_tested_as.assert_not_called()


@mock.patch("research.graph.cli.GraphStore.from_env")
@mock.patch("research.graph.cli.NeoConnector.is_available")
class TestHypothesisBranchedFromCombined:
    """E2E tests for QWS-HF-001 Fix 2: single-call --hypothesis title --branched-from."""

    def _record_args(self) -> mock.MagicMock:
        args = mock.MagicMock()
        args.file = None
        args.bundle = None
        args.oos = None
        args.timeout_seconds = 3
        args.similarity_threshold = None
        return args

    def test_title_with_branched_from_creates_node_and_edge(
        self, mock_is_available, mock_store_factory
    ) -> None:
        """Title string + --branched-from creates Hypothesis node then BRANCHED_FROM edge."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.create_hypothesis.return_value = "abc123def456"
        mock_store.link_hypothesis_branched_from.return_value = True
        mock_store_factory.return_value = mock_store

        args = self._record_args()
        args.hypothesis = "bear liquidity sweep variant"
        args.tested_as = None
        args.branched_from = "abc000000000"
        args.rationale = "prior run showed drawdown; tighten stops"
        args.status = None

        exit_code = cmd_record(args)

        assert exit_code == 0
        assert mock_store.create_hypothesis.call_count == 1
        assert mock_store.link_hypothesis_branched_from.call_count == 1

    def test_existing_id_with_branched_from_skips_node_creation(
        self, mock_is_available, mock_store_factory
    ) -> None:
        """12-char hex hypothesis_id + --branched-from only creates edge (existing node path)."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store.link_hypothesis_branched_from.return_value = True
        mock_store_factory.return_value = mock_store

        args = self._record_args()
        args.hypothesis = "a0e7380e58e8"  # 12-char hex
        args.tested_as = None
        args.branched_from = "abc000000000"
        args.rationale = "some rationale"
        args.status = None

        exit_code = cmd_record(args)

        assert exit_code == 0
        mock_store.create_hypothesis.assert_not_called()
        assert mock_store.link_hypothesis_branched_from.call_count == 1

    def test_title_with_branched_from_missing_rationale_exits_1(
        self, mock_is_available, mock_store_factory
    ) -> None:
        """Missing --rationale when combining title + --branched-from exits 1."""
        mock_is_available.return_value = True
        mock_store = mock.MagicMock()
        mock_store_factory.return_value = mock_store

        args = self._record_args()
        args.hypothesis = "bear liquidity sweep variant"
        args.tested_as = None
        args.branched_from = "abc000000000"
        args.rationale = None
        args.status = None

        exit_code = cmd_record(args)

        assert exit_code == 1
        mock_store.create_hypothesis.assert_not_called()
