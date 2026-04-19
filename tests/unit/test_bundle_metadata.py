# mypy: ignore-errors
"""Unit tests for QWS-0907: trial_metadata bundle ingest and store write."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from research.graph.cli import _cmd_bundle
from research.graph.store import GraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CSV_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "strategies"
_STRATEGY_FIXTURE = _CSV_DIR / "strategy_source_fixture.py"

_MINIMAL_MANIFEST_BASE: dict = {
    "trial": "regime_sweep",
    "run_ts": "20260413-120000",
    "files": {
        "csv": "baseline_results.csv",
        "csv_kind": "baseline_csv",
    },
}


def _make_store_mock(persist_run_ids: list[str] | None = None):
    """Return a mock GraphStore whose persist_artifact returns known run IDs."""
    mock_store = MagicMock(spec=GraphStore)
    run_ids = persist_run_ids or ["aaa000000001"]
    outcomes = [
        MagicMock(run_id=rid, status="recorded", evidence_score=2.5, champion_id=None)
        for rid in run_ids
    ]
    mock_store.persist_artifact.return_value = MagicMock(evolution=outcomes)
    return mock_store


def _minimal_csv(tmp_path: Path) -> Path:
    """Write a minimal valid baseline CSV; returns path."""
    csv_content = (
        "instrument,timeframe,direction,logic_type,"
        "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
        "first_trade_ts,last_trade_ts\n"
        "CL,1H,bear,liquidity-sweep,"
        "40,0.60,1.5,2.5,-0.12,"
        "2024-01-02T10:00:00Z,2025-06-01T16:00:00Z\n"
    )
    p = tmp_path / "baseline_results.csv"
    p.write_text(csv_content)
    return p


def _run_bundle(tmp_path: Path, mock_store: MagicMock) -> int:
    args = argparse.Namespace(
        bundle=str(tmp_path),
        offline=False,
        dry_run=False,
        timeout_seconds=3,
        repo_root=None,
        file=None,
        kind=None,
        source_file=None,
        regime=None,
        rationale=None,
    )
    with (
        patch("research.graph.cli.NeoConnector") as mock_connector,
        patch("research.graph.cli.GraphStore.from_env", return_value=mock_store),
    ):
        mock_connector.return_value.is_available.return_value = True
        return _cmd_bundle(args)


# ---------------------------------------------------------------------------
# AC1: trial_metadata present → write_trial_metadata called with correct args
# ---------------------------------------------------------------------------


class TestTrialMetadataWritten:
    def test_write_trial_metadata_called_when_present(self, tmp_path: Path):
        manifest = {
            **_MINIMAL_MANIFEST_BASE,
            "trial_metadata": {"atr_bucket": "high", "avg_atr": "2.3"},
        }
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock(["aaa000000001"])
        rc = _run_bundle(tmp_path, mock_store)

        assert rc == 0
        mock_store.write_trial_metadata.assert_called_once_with(
            ["aaa000000001"], {"atr_bucket": "high", "avg_atr": "2.3"}
        )

    def test_trial_metadata_values_passed_exactly(self, tmp_path: Path):
        meta = {"atr_bucket": "low", "avg_atr": "0.5", "regime_label": "trend_up"}
        manifest = {**_MINIMAL_MANIFEST_BASE, "trial_metadata": meta}
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock(["aaa000000001"])
        rc = _run_bundle(tmp_path, mock_store)

        assert rc == 0
        _, kwargs = mock_store.write_trial_metadata.call_args
        # called positionally; check both args
        call_args = mock_store.write_trial_metadata.call_args[0]
        assert call_args[1] == meta


# ---------------------------------------------------------------------------
# AC2: no trial_metadata field → write_trial_metadata NOT called
# ---------------------------------------------------------------------------


class TestTrialMetadataAbsent:
    def test_no_trial_metadata_key_skips_write(self, tmp_path: Path):
        (tmp_path / "bundle.json").write_text(json.dumps(_MINIMAL_MANIFEST_BASE))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock(["aaa000000001"])
        rc = _run_bundle(tmp_path, mock_store)

        assert rc == 0
        mock_store.write_trial_metadata.assert_not_called()

    def test_ingest_succeeds_without_trial_metadata(self, tmp_path: Path):
        (tmp_path / "bundle.json").write_text(json.dumps(_MINIMAL_MANIFEST_BASE))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock()
        rc = _run_bundle(tmp_path, mock_store)

        assert rc == 0


# ---------------------------------------------------------------------------
# AC3: trial_metadata > 10KB → WARNING printed, write_trial_metadata NOT called
# ---------------------------------------------------------------------------


class TestTrialMetadataSizeGuard:
    def test_oversized_metadata_skips_write(self, tmp_path: Path, capsys):
        # Build a dict that serializes to > 10240 bytes
        big_meta = {f"key_{i}": "x" * 50 for i in range(300)}
        assert len(json.dumps(big_meta, separators=(",", ":"))) > 10240

        manifest = {**_MINIMAL_MANIFEST_BASE, "trial_metadata": big_meta}
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock(["aaa000000001"])
        rc = _run_bundle(tmp_path, mock_store)

        assert rc == 0
        mock_store.write_trial_metadata.assert_not_called()

    def test_oversized_metadata_prints_warning(self, tmp_path: Path, capsys):
        big_meta = {f"key_{i}": "x" * 50 for i in range(300)}
        manifest = {**_MINIMAL_MANIFEST_BASE, "trial_metadata": big_meta}
        (tmp_path / "bundle.json").write_text(json.dumps(manifest))
        _minimal_csv(tmp_path)

        mock_store = _make_store_mock()
        _run_bundle(tmp_path, mock_store)

        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "10KB" in captured.err


# ---------------------------------------------------------------------------
# AC4: write_trial_metadata store method — calls correct Cypher with correct params
# ---------------------------------------------------------------------------


class TestWriteTrialMetadataStore:
    def _make_store(self) -> GraphStore:
        with patch("research.graph.store.GraphDatabase.driver"):
            return GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")

    def test_calls_cypher_with_correct_params(self):
        from research.graph.cypher import TRIAL_METADATA_WRITE_QUERY

        store = self._make_store()
        run_ids = ["abc123def456", "def456abc789"]
        trial_metadata = {"atr_bucket": "high", "avg_atr": "2.3"}

        captured: dict = {}

        class FakeTx:
            def run(self, query, **kwargs):
                captured["query"] = query
                captured["kwargs"] = kwargs
                return MagicMock(consume=lambda: None)

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute_write(self, fn):
                fn(FakeTx())

        store._driver.session = MagicMock(return_value=FakeSession())
        store.write_trial_metadata(run_ids, trial_metadata)

        assert captured["query"] == TRIAL_METADATA_WRITE_QUERY
        assert captured["kwargs"]["run_ids"] == run_ids
        assert captured["kwargs"]["trial_metadata"] == trial_metadata

    def test_empty_run_ids_skips_neo4j_call(self):
        store = self._make_store()
        store._driver.session = MagicMock()

        store.write_trial_metadata([], {"atr_bucket": "high"})

        store._driver.session.assert_not_called()

    def test_write_error_raises_store_infra_error(self):
        from neo4j.exceptions import ServiceUnavailable

        from research.graph.store import StoreInfraError

        store = self._make_store()

        class BrokenSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute_write(self, fn):
                raise ServiceUnavailable("Neo4j down")

        store._driver.session = MagicMock(return_value=BrokenSession())
        with pytest.raises(StoreInfraError):
            store.write_trial_metadata(["abc123def456"], {"atr_bucket": "high"})
