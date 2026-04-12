"""Unit tests for Story 6 bundle ingestion: manifest reading, CLI, and store patch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from research.graph.cli import _cmd_bundle, _read_bundle_manifest
from research.graph.store import GraphStore

_STRATEGY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "strategies" / "strategy_source_fixture.py"
)


# ---------------------------------------------------------------------------
# _read_bundle_manifest
# ---------------------------------------------------------------------------


class TestReadBundleManifest:
    def test_returns_manifest_when_valid(self, tmp_path: Path):
        manifest = {
            "trial": "liquidity_sweep_baseline",
            "run_ts": "20260405-143022",
            "files": {
                "csv": "baseline_results.csv",
                "csv_kind": "baseline_csv",
                "html": "index.html",
            },
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        result = _read_bundle_manifest(tmp_path)

        assert result["trial"] == "liquidity_sweep_baseline"
        assert result["files"]["csv"] == "baseline_results.csv"
        assert result["files"]["csv_kind"] == "baseline_csv"
        assert result["files"]["html"] == "index.html"

    def test_raises_file_not_found_when_manifest_absent(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="bundle.json"):
            _read_bundle_manifest(tmp_path)

    def test_error_message_names_the_expected_file(self, tmp_path: Path):
        """Error must name bundle.json so the operator knows exactly what to create."""
        with pytest.raises(FileNotFoundError) as exc_info:
            _read_bundle_manifest(tmp_path)
        assert "bundle.json" in str(exc_info.value)

    def test_raises_value_error_when_csv_missing(self, tmp_path: Path):
        manifest = {
            "trial": "x",
            "run_ts": "20260405-000000",
            "files": {"csv_kind": "baseline_csv"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="csv"):
            _read_bundle_manifest(tmp_path)

    def test_raises_value_error_when_csv_kind_missing(self, tmp_path: Path):
        manifest = {"trial": "x", "run_ts": "20260405-000000", "files": {"csv": "results.csv"}}
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="csv_kind"):
            _read_bundle_manifest(tmp_path)

    def test_html_field_is_optional(self, tmp_path: Path):
        manifest = {
            "trial": "x",
            "run_ts": "20260405-000000",
            "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        result = _read_bundle_manifest(tmp_path)
        assert result["files"].get("html") is None


# ---------------------------------------------------------------------------
# _cmd_bundle: error paths (no Neo4j needed)
# ---------------------------------------------------------------------------


class TestCmdBundleErrors:
    def _make_args(self, bundle: str, offline: bool = False, dry_run: bool = False):
        import argparse

        return argparse.Namespace(
            bundle=bundle,
            offline=offline,
            dry_run=dry_run,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
        )

    def test_returns_1_when_bundle_dir_missing(self, tmp_path: Path):
        args = self._make_args(str(tmp_path / "nonexistent"))
        rc = _cmd_bundle(args)
        assert rc == 1

    def test_returns_1_when_manifest_absent(self, tmp_path: Path):
        args = self._make_args(str(tmp_path))
        rc = _cmd_bundle(args)
        assert rc == 1

    def test_returns_1_when_offline_mode_requested(self, tmp_path: Path):
        args = self._make_args(str(tmp_path), offline=True)
        rc = _cmd_bundle(args)
        assert rc == 1

    def test_dry_run_returns_0_with_valid_csv(self, tmp_path: Path):
        """Dry-run with a parseable CSV should exit 0 without touching Neo4j."""
        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "32,0.65625,2.136028,4.58565,-0.028805,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n"
        )
        (tmp_path / "results.csv").write_text(csv_content)
        manifest = {
            "trial": "test",
            "run_ts": "20260405-120000",
            "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        args = self._make_args(str(tmp_path), dry_run=True)
        rc = _cmd_bundle(args)
        assert rc == 0

    def test_source_file_attaches_family_id_on_bundle(self, tmp_path: Path):
        """--source-file on --bundle sets family_id on the Strategy before persist."""
        import argparse
        from unittest.mock import MagicMock, patch

        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "32,0.65625,2.136028,4.58565,-0.028805,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n"
        )
        csv_path = tmp_path / "results.csv"
        csv_path.write_text(csv_content)

        source_py = _STRATEGY_FIXTURE

        manifest = {
            "trial": "test",
            "run_ts": "20260405-120000",
            "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        captured_artifact = {}

        def fake_persist(artifact, **kwargs):
            captured_artifact["family_id"] = artifact.strategy.family_id
            result = MagicMock()
            result.evolution = []
            return result

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=str(source_py),
        )

        with (
            patch("research.graph.cli.NeoConnector") as mock_connector,
            patch("research.graph.cli.GraphStore.from_env") as mock_store_factory,
        ):
            mock_connector.return_value.is_available.return_value = True
            mock_store = MagicMock()
            mock_store.persist_artifact.side_effect = fake_persist
            mock_store_factory.return_value.__enter__ = MagicMock(return_value=mock_store)
            mock_store_factory.return_value.__exit__ = MagicMock(return_value=False)
            mock_store_factory.return_value = mock_store

            rc = _cmd_bundle(args)

        assert rc == 0
        assert captured_artifact["family_id"] is not None, (
            "family_id must be set when --source-file is provided"
        )

    def test_bundle_without_source_file_leaves_family_id_none(self, tmp_path: Path):
        """Omitting --source-file leaves family_id as None (existing behavior unchanged)."""
        import argparse
        from unittest.mock import MagicMock, patch

        csv_content = (
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "32,0.65625,2.136028,4.58565,-0.028805,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n"
        )
        (tmp_path / "results.csv").write_text(csv_content)
        manifest = {
            "trial": "test",
            "run_ts": "20260405-120000",
            "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))

        captured_artifact = {}

        def fake_persist(artifact, **kwargs):
            captured_artifact["family_id"] = artifact.strategy.family_id
            result = MagicMock()
            result.evolution = []
            return result

        args = argparse.Namespace(
            bundle=str(tmp_path),
            offline=False,
            dry_run=False,
            timeout_seconds=3,
            repo_root=None,
            file=None,
            kind=None,
            source_file=None,
        )

        with (
            patch("research.graph.cli.NeoConnector") as mock_connector,
            patch("research.graph.cli.GraphStore.from_env") as mock_store_factory,
        ):
            mock_connector.return_value.is_available.return_value = True
            mock_store = MagicMock()
            mock_store.persist_artifact.side_effect = fake_persist
            mock_store_factory.return_value = mock_store

            rc = _cmd_bundle(args)

        assert rc == 0
        assert captured_artifact["family_id"] is None, (
            "family_id must remain None when --source-file is not provided"
        )


# ---------------------------------------------------------------------------
# patch_run_html_path
# ---------------------------------------------------------------------------


class TestPatchRunHtmlPath:
    def _make_store(self) -> GraphStore:
        with patch("research.graph.store.GraphDatabase.driver"):
            return GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")

    def test_calls_correct_cypher_with_correct_params(self):
        from research.graph.cypher import PATCH_RUN_HTML_PATH_QUERY

        store = self._make_store()
        run_id = "abc123def456"
        html_path = "/path/to/report.html"

        captured = {}

        class FakeTx:
            def run(self, query, **kwargs):
                captured["query"] = query
                captured["kwargs"] = kwargs
                result = MagicMock()
                result.__iter__ = MagicMock(return_value=iter([{"run_id": run_id}]))
                return result

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute_write(self, fn):
                return list(fn(FakeTx()))

        store._driver.session = MagicMock(return_value=FakeSession())
        store.patch_run_html_path(run_id, html_path)

        assert captured["query"] == PATCH_RUN_HTML_PATH_QUERY
        assert captured["kwargs"]["run_id"] == run_id
        assert captured["kwargs"]["html_path"] == html_path

    def test_returns_true_when_run_found(self):
        store = self._make_store()

        class FakeTx:
            def run(self, *args, **kwargs):
                result = MagicMock()
                result.__iter__ = MagicMock(return_value=iter([{"run_id": "abc"}]))
                return result

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute_write(self, fn):
                return list(fn(FakeTx()))

        store._driver.session = MagicMock(return_value=FakeSession())
        assert store.patch_run_html_path("abc", "/path.html") is True

    def test_returns_false_when_run_not_found(self):
        store = self._make_store()

        class FakeTx:
            def run(self, *args, **kwargs):
                result = MagicMock()
                result.__iter__ = MagicMock(return_value=iter([]))
                return result

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute_write(self, fn):
                return list(fn(FakeTx()))

        store._driver.session = MagicMock(return_value=FakeSession())
        assert store.patch_run_html_path("no-such-run", "/path.html") is False
