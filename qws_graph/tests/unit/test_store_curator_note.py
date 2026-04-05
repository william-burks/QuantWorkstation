"""Unit tests for curator_note normalization in GraphStore._persist_csv."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import GraphStore


def _make_store() -> GraphStore:
    """Return a GraphStore with a patched driver (no real Neo4j required)."""
    with patch("research.graph.store.GraphDatabase.driver"):
        store = GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")
    return store


def _make_payload(curator_note_value) -> dict:
    """Build a minimal _persist_csv payload with the given curator_note."""
    return {
        "strategy": {
            "strategy_id": "cl-1h-bear-liquidity-sweep",
            "instrument": "CL",
            "timeframe": "1H",
            "direction": "bear",
            "logic_type": "liquidity-sweep",
            "family_id": None,
        },
        "runs": [
            {
                "run_id": "abc123def456",
                "strategy_id": "cl-1h-bear-liquidity-sweep",
                "timestamp": "2026-04-05T00:00:00+00:00",
                "sharpe": 1.5,
                "profit_factor": 1.8,
                "win_rate": 0.55,
                "max_drawdown": -0.08,
                "total_trades": 42,
                "total_r": 6.3,
                "artifact_path": "research/trials/futures/liquidity_sweep/golden_results.csv",
                "curator_note": curator_note_value,
                "provenance": {
                    "artifact_path": "research/trials/futures/liquidity_sweep/golden_results.csv",
                    "artifact_hash": "deadbeef" * 8,
                    "artifact_mtime_iso": "2026-04-05T10:00:00Z",
                    "ingested_at": "2026-04-05T10:00:00+00:00",
                    "parser_version": "v1",
                },
            }
        ],
        "configs": [
            {
                "config_id": "fedcba987654",
                "params_json": {"target_r": 1.25},
                "risk_params": {},
            }
        ],
    }


class TestCuratorNoteNormalization:
    """Verify that _persist_csv always writes curator_note as "" when None."""

    def test_curator_note_none_becomes_empty_string(self):
        """None curator_note must be written as "" not null."""
        store = _make_store()
        captured_rows: list[dict] = []

        def fake_session_write(tx_fn):
            # Capture rows passed to the Cypher query
            class FakeTx:
                def run(self, query, rows=None, **kwargs):
                    if rows is not None:
                        captured_rows.extend(rows)
                    return MagicMock(consume=MagicMock())
            tx_fn(FakeTx())

        fake_session = MagicMock()
        fake_session.execute_write.side_effect = fake_session_write

        payload = _make_payload(curator_note_value=None)
        store._persist_csv(fake_session, payload)

        assert len(captured_rows) == 1
        assert captured_rows[0]["run"]["curator_note"] == "", (
            "curator_note must be '' (empty string) when ingestion has no AI curation — "
            "Neo4j removes null-set properties entirely"
        )

    def test_curator_note_existing_value_preserved(self):
        """Non-None curator_note must pass through truncation unchanged (within limit)."""
        store = _make_store()
        captured_rows: list[dict] = []

        def fake_session_write(tx_fn):
            class FakeTx:
                def run(self, query, rows=None, **kwargs):
                    if rows is not None:
                        captured_rows.extend(rows)
                    return MagicMock(consume=MagicMock())
            tx_fn(FakeTx())

        fake_session = MagicMock()
        fake_session.execute_write.side_effect = fake_session_write

        note = "Strong Sharpe driven by tight NY_PRE session filter."
        payload = _make_payload(curator_note_value=note)
        store._persist_csv(fake_session, payload)

        assert captured_rows[0]["run"]["curator_note"] == note

    def test_curator_note_empty_string_preserved(self):
        """Explicit empty-string curator_note must remain ""."""
        store = _make_store()
        captured_rows: list[dict] = []

        def fake_session_write(tx_fn):
            class FakeTx:
                def run(self, query, rows=None, **kwargs):
                    if rows is not None:
                        captured_rows.extend(rows)
                    return MagicMock(consume=MagicMock())
            tx_fn(FakeTx())

        fake_session = MagicMock()
        fake_session.execute_write.side_effect = fake_session_write

        payload = _make_payload(curator_note_value="")
        store._persist_csv(fake_session, payload)

        assert captured_rows[0]["run"]["curator_note"] == ""
