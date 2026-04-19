"""Unit tests for PaperLibrary and VectorIndex."""

from __future__ import annotations

import tempfile

from qws_researcher import Paper


def _make_paper(paper_id: str, title: str, abstract: str = "", source: str = "arxiv") -> Paper:
    return Paper(
        id=paper_id,
        title=title,
        authors=["Test Author"],
        abstract=abstract or f"Abstract for {title}",
        source=source,
        url=f"https://example.com/{paper_id}",
        fetched_at="2023-01-01T00:00:00+00:00",
    )


class TestPaperLibrary:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()

    def test_add_and_get_roundtrip(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        paper = _make_paper("arxiv:2301.00001", "Test Paper on Volatility")

        result = lib.add(paper)
        assert result is True

        retrieved = lib.get("arxiv:2301.00001")
        assert retrieved is not None
        assert retrieved.title == "Test Paper on Volatility"
        assert retrieved.source == "arxiv"

    def test_add_dedup_returns_false_for_existing(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        paper = _make_paper("arxiv:2301.00001", "Test Paper")

        first = lib.add(paper)
        second = lib.add(paper)

        assert first is True
        assert second is False

    def test_get_returns_none_for_missing(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        assert lib.get("arxiv:nonexistent") is None

    def test_list_all_returns_all_papers(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        lib.add(_make_paper("arxiv:0001", "Paper One"))
        lib.add(_make_paper("arxiv:0002", "Paper Two"))
        lib.add(_make_paper("pmid:11111", "Paper Three", source="pubmed"))

        all_papers = lib.list_all()
        assert len(all_papers) == 3

    def test_delete_removes_paper(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        lib.add(_make_paper("arxiv:0001", "Paper One"))
        lib.delete("arxiv:0001")
        assert lib.get("arxiv:0001") is None

    def test_index_persists_across_instances(self):
        from qws_researcher.store.library import PaperLibrary

        lib1 = PaperLibrary(data_dir=self._tmpdir)
        lib1.add(_make_paper("arxiv:0001", "Persistent Paper"))

        lib2 = PaperLibrary(data_dir=self._tmpdir)
        retrieved = lib2.get("arxiv:0001")
        assert retrieved is not None
        assert retrieved.title == "Persistent Paper"

    def test_stats_returns_correct_counts(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        lib.add(_make_paper("arxiv:0001", "Paper One"))
        lib.add(_make_paper("arxiv:0002", "Paper Two"))
        lib.add(_make_paper("pmid:11111", "Paper Three", source="pubmed"))

        stats = lib.stats()
        assert stats["total_papers"] == 3
        assert stats["by_source"]["arxiv"] == 2
        assert stats["by_source"]["pubmed"] == 1


class TestVectorSearch:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()

    def test_vector_search_returns_relevant_results(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)

        papers = [
            _make_paper(
                "arxiv:0001",
                "Realized Volatility and HAR Model",
                abstract="We study realized volatility using the HAR model with intraday returns.",
            ),
            _make_paper(
                "arxiv:0002",
                "Deep Learning for Stock Prediction",
                abstract="Neural networks applied to stock price prediction using LSTM architecture.",
            ),
            _make_paper(
                "arxiv:0003",
                "High-frequency Trading Microstructure",
                abstract="Analysis of order book dynamics and market microstructure at high frequency.",
            ),
        ]

        for p in papers:
            lib.add(p)

        # Search for something related to volatility
        results = lib.search_semantic("volatility forecasting HAR", n=3)

        assert len(results) >= 1
        # The volatility paper should rank highest
        assert results[0].id == "arxiv:0001"

    def test_vector_search_empty_library(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        results = lib.search_semantic("anything")
        assert results == []

    def test_stats_includes_vector_chunk_count(self):
        from qws_researcher.store.library import PaperLibrary

        lib = PaperLibrary(data_dir=self._tmpdir)
        lib.add(_make_paper("arxiv:0001", "Test", abstract="x" * 1000))

        stats = lib.stats()
        assert "vector_chunks" in stats
        assert stats["vector_chunks"] > 0
