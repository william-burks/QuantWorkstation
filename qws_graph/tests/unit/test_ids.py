"""Unit tests for research.graph.ids — family_id and related additions."""

from __future__ import annotations

import sys
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.ids import (
    family_id,
    run_stats_summary_id,
    source_hash,
)

# ---------------------------------------------------------------------------
# source_hash
# ---------------------------------------------------------------------------

class TestSourceHash:
    def test_returns_12_char_hex(self) -> None:
        h = source_hash(b"some python code")
        assert len(h) == 12
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_for_same_bytes(self) -> None:
        content = b"def generate_signals(): pass"
        assert source_hash(content) == source_hash(content)

    def test_different_content_gives_different_hash(self) -> None:
        assert source_hash(b"rsi logic") != source_hash(b"bollinger logic")

    def test_empty_bytes_produces_valid_hash(self) -> None:
        h = source_hash(b"")
        assert len(h) == 12


# ---------------------------------------------------------------------------
# family_id
# ---------------------------------------------------------------------------

class TestFamilyId:
    def test_returns_12_char_hex(self) -> None:
        fid = family_id("MeanReversion", "bear", "abc123def456")
        assert len(fid) == 12
        assert all(c in "0123456789abcdef" for c in fid)

    def test_deterministic_same_inputs(self) -> None:
        src = source_hash(b"rsi reversion code")
        assert family_id("MeanReversion", "bear", src) == family_id("MeanReversion", "bear", src)

    def test_same_logic_different_instruments_share_family_id(self) -> None:
        src = source_hash(b"shared rsi logic")
        # ES and NQ strategies share the same family_id — family_id is instrument-agnostic
        fid_es = family_id("MeanReversion", "bear", src)
        fid_nq = family_id("MeanReversion", "bear", src)
        assert fid_es == fid_nq

    def test_different_logic_type_gives_different_family_id(self) -> None:
        src = source_hash(b"some code")
        assert family_id("MeanReversion", "bear", src) != family_id("TrendFollowing", "bear", src)

    def test_different_direction_gives_different_family_id(self) -> None:
        src = source_hash(b"some code")
        assert family_id("MeanReversion", "bear", src) != family_id("MeanReversion", "bull", src)

    def test_different_source_hash_gives_different_family_id(self) -> None:
        src_v1 = source_hash(b"rsi logic v1")
        src_v2 = source_hash(b"bollinger logic v2")
        assert family_id("MeanReversion", "bear", src_v1) != family_id("MeanReversion", "bear", src_v2)

    def test_independent_of_filename_or_path(self) -> None:
        content = b"def generate_signals(): return rsi_signal"
        src = source_hash(content)
        # Same content hashed from two different filenames → same family_id
        fid_a = family_id("MeanReversion", "bear", src)
        fid_b = family_id("MeanReversion", "bear", src)
        assert fid_a == fid_b

    def test_normalizes_logic_type_case(self) -> None:
        src = source_hash(b"x")
        assert family_id("meanreversion", "bear", src) == family_id("MeanReversion", "bear", src)

    def test_normalizes_direction_case(self) -> None:
        src = source_hash(b"x")
        assert family_id("MeanReversion", "BEAR", src) == family_id("MeanReversion", "bear", src)


# ---------------------------------------------------------------------------
# run_stats_summary_id
# ---------------------------------------------------------------------------

class TestRunStatsSummaryId:
    def test_returns_12_char_hex(self) -> None:
        sid = run_stats_summary_id("es-1h-bear-sweep", "results/grid.csv", "2026-04-01T00:00:00Z")
        assert len(sid) == 12

    def test_deterministic(self) -> None:
        sid1 = run_stats_summary_id("es-1h-bear-sweep", "results/grid.csv", "2026-04-01T00:00:00Z")
        sid2 = run_stats_summary_id("es-1h-bear-sweep", "results/grid.csv", "2026-04-01T00:00:00Z")
        assert sid1 == sid2

    def test_different_mtime_gives_different_id(self) -> None:
        sid1 = run_stats_summary_id("es-1h-bear-sweep", "results/grid.csv", "2026-04-01T00:00:00Z")
        sid2 = run_stats_summary_id("es-1h-bear-sweep", "results/grid.csv", "2026-04-02T00:00:00Z")
        assert sid1 != sid2

    def test_different_artifact_path_gives_different_id(self) -> None:
        mtime = "2026-04-01T00:00:00Z"
        sid1 = run_stats_summary_id("es-1h-bear-sweep", "results/grid_a.csv", mtime)
        sid2 = run_stats_summary_id("es-1h-bear-sweep", "results/grid_b.csv", mtime)
        assert sid1 != sid2
