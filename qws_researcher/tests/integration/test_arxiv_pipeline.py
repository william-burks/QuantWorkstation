"""
Integration tests — require real network access.
Run with: uv run pytest tests/integration/ -m integration -v
Skipped by default.
"""

from __future__ import annotations

import tempfile

import pytest


@pytest.mark.integration
def test_arxiv_search_and_full_pipeline() -> None:
    """Search arXiv for a known paper and run the full fetch pipeline."""
    import tempfile

    from qws_researcher.sources import arxiv as arxiv_src

    with tempfile.TemporaryDirectory() as tmpdir:
        # Search for the HAR model paper (Corsi 2009) — well-known in quant finance
        papers = arxiv_src.search(
            "HAR realized volatility Corsi",
            categories=["q-fin.ST"],
            max_results=5,
            data_dir=tmpdir,
        )
        assert len(papers) > 0, "Expected at least one result for HAR volatility search"

        paper = papers[0]
        assert paper.id.startswith("arxiv:")
        assert paper.title is not None and len(paper.title) > 5
        assert paper.abstract

        # Fetch PDF
        pdf_path = arxiv_src.fetch_pdf(paper.id, data_dir=tmpdir)
        assert pdf_path is not None, "Expected PDF download to succeed"

        # Extract text
        from qws_researcher.extract import extract_text

        assert pdf_path is not None
        text = extract_text(pdf_path)
        assert len(text) > 500, "Expected extracted text to be non-trivial"


@pytest.mark.integration
def test_library_full_roundtrip() -> None:
    """Add papers to library, search, verify persistence."""
    from qws_researcher.sources import arxiv as arxiv_src
    from qws_researcher.store.library import PaperLibrary

    with tempfile.TemporaryDirectory() as tmpdir:
        lib = PaperLibrary(data_dir=tmpdir)

        papers = arxiv_src.search(
            "realized volatility forecasting",
            categories=["q-fin.ST"],
            max_results=3,
            data_dir=tmpdir,
        )
        assert len(papers) >= 1

        for p in papers:
            lib.add(p)

        stats = lib.stats()
        assert stats["total_papers"] == len(papers)

        # Semantic search
        results = lib.search_semantic("volatility HAR model", n=3)
        assert len(results) >= 1
