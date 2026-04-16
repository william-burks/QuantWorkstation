"""Unit tests for paper sources — all network calls are mocked."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from qws_researcher import Paper

# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

_ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>HAR Model for Realized Volatility</title>
    <summary>We study realized volatility using HAR model.</summary>
    <published>2023-01-01T00:00:00Z</published>
    <author><name>John Doe</name></author>
    <author><name>Jane Smith</name></author>
    <category term="q-fin.ST"/>
    <link type="application/pdf" href="https://arxiv.org/pdf/2301.00001"/>
  </entry>
</feed>"""


def _mock_httpx_response(content: bytes, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def test_arxiv_search_returns_papers():
    import time

    import papers.sources.arxiv as arxiv_mod

    arxiv_mod._last_request = time.monotonic()  # skip throttle sleep

    mock_resp = _mock_httpx_response(_ATOM_FEED)
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("papers.sources.arxiv.httpx.Client", return_value=mock_client):
        papers_list = arxiv_mod.search("realized volatility HAR", data_dir="/tmp/test_data")

    assert len(papers_list) == 1
    p = papers_list[0]
    assert p.id == "arxiv:2301.00001"
    assert p.title == "HAR Model for Realized Volatility"
    assert p.source == "arxiv"
    assert "John Doe" in p.authors
    assert p.pdf_path == "url:https://arxiv.org/pdf/2301.00001"


def test_arxiv_search_with_categories():
    import time

    import papers.sources.arxiv as arxiv_mod

    arxiv_mod._last_request = time.monotonic()

    mock_resp = _mock_httpx_response(_ATOM_FEED)
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("papers.sources.arxiv.httpx.Client", return_value=mock_client):
        papers_list = arxiv_mod.search(
            "volatility", categories=["q-fin.ST", "stat.ML"], data_dir="/tmp/test_data"
        )

    call_kwargs = mock_client.get.call_args
    params = call_kwargs[1]["params"] if call_kwargs[1] else call_kwargs[0][1]
    assert "cat:" in params["search_query"]
    assert len(papers_list) == 1


def test_arxiv_search_returns_empty_on_error():
    import time

    import papers.sources.arxiv as arxiv_mod

    arxiv_mod._last_request = time.monotonic()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = Exception("Network error")

    with patch("papers.sources.arxiv.httpx.Client", return_value=mock_client):
        result = arxiv_mod.search("volatility", data_dir="/tmp/test_data")

    assert result == []


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

def _make_bulk_response(title="Test Paper", paper_id="abc123def456", external_ids=None):
    return {
        "data": [
            {
                "paperId": paper_id,
                "externalIds": external_ids or {},
                "title": title,
                "abstract": "Abstract text here.",
                "authors": [{"authorId": "1", "name": "Author One"}],
                "year": 2023,
                "citationCount": 42,
                "openAccessPdf": None,
                "fieldsOfStudy": ["Finance"],
            }
        ],
        "token": None,
    }


def test_semantic_scholar_search_returns_papers():
    mock_response = MagicMock()
    mock_response.json.return_value = _make_bulk_response()
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as MockClient, patch("time.sleep"):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        import importlib

        import papers.sources.semantic as sem_mod
        importlib.reload(sem_mod)

        papers_list = sem_mod.search("realized volatility", data_dir="/tmp/test_data")

    assert len(papers_list) == 1
    p = papers_list[0]
    assert p.id == "s2:abc123def456"
    assert p.citations == 42
    assert p.source == "semantic_scholar"


def test_semantic_scholar_search_promotes_arxiv_id():
    mock_response = MagicMock()
    mock_response.json.return_value = _make_bulk_response(
        paper_id="abc123", external_ids={"ArXiv": "2301.99999"}
    )
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as MockClient, patch("time.sleep"):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        import importlib

        import papers.sources.semantic as sem_mod
        importlib.reload(sem_mod)

        papers_list = sem_mod.search("realized volatility", data_dir="/tmp/test_data")

    assert papers_list[0].id == "arxiv:2301.99999"
    assert "arxiv.org" in papers_list[0].url


def test_semantic_scholar_search_uses_bulk_endpoint():
    mock_response = MagicMock()
    mock_response.json.return_value = _make_bulk_response()
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as MockClient, patch("time.sleep"):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        import importlib

        import papers.sources.semantic as sem_mod
        importlib.reload(sem_mod)

        sem_mod.search("realized volatility", data_dir="/tmp/test_data")

    call_args = instance.get.call_args
    url = call_args[0][0]
    assert "search/bulk" in url
    params = call_args[1]["params"]
    assert "fieldsOfStudy" in params
    assert "Finance" in params["fieldsOfStudy"]


def test_semantic_scholar_search_returns_empty_on_error():
    with patch("httpx.Client") as MockClient, patch("time.sleep"):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.side_effect = Exception("API error")

        import importlib

        import papers.sources.semantic as sem_mod
        importlib.reload(sem_mod)

        result = sem_mod.search("volatility", data_dir="/tmp/test_data")

    assert result == []


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------

_PUBMED_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Econophysics of volatility</ArticleTitle>
        <Abstract>
          <AbstractText>We study stock market fluctuations.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Doe</LastName>
            <ForeName>John</ForeName>
          </Author>
        </AuthorList>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2020</Year>
              <Month>03</Month>
            </PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

_PUBMED_SEARCH_RESULT = {
    "IdList": ["12345678"],
    "Count": "1",
    "RetMax": "20",
    "RetStart": "0",
}


def test_pubmed_search_returns_papers():
    with patch("Bio.Entrez.esearch") as mock_esearch, \
         patch("Bio.Entrez.read") as mock_read, \
         patch("Bio.Entrez.efetch") as mock_efetch:

        mock_read.return_value = _PUBMED_SEARCH_RESULT
        mock_esearch.return_value = MagicMock()
        mock_efetch.return_value = io.BytesIO(_PUBMED_XML)

        from qws_researcher.sources import pubmed as pubmed_mod
        result = pubmed_mod.search("volatility econophysics", max_results=5)

    assert len(result) == 1
    p = result[0]
    assert p.id == "pmid:12345678"
    assert "Econophysics" in p.title
    assert p.source == "pubmed"
    assert "John Doe" in p.authors


def test_pubmed_econophysics_filter_is_appended():
    """Verify the econophysics filter is always appended to queries."""
    with patch("Bio.Entrez.esearch") as mock_esearch, \
         patch("Bio.Entrez.read") as mock_read:

        mock_read.return_value = {"IdList": []}
        mock_esearch.return_value = MagicMock()

        from qws_researcher.sources import pubmed as pubmed_mod
        pubmed_mod.search("my query", max_results=5)

    call_kwargs = mock_esearch.call_args[1]
    assert "econophysics" in call_kwargs["term"]
    assert "my query" in call_kwargs["term"]


def test_pubmed_search_returns_empty_on_error():
    with patch("Bio.Entrez.esearch") as mock_esearch:
        mock_esearch.side_effect = Exception("Network error")

        from qws_researcher.sources import pubmed as pubmed_mod
        result = pubmed_mod.search("volatility")

    assert result == []


# ---------------------------------------------------------------------------
# Unpaywall
# ---------------------------------------------------------------------------

def _make_unpaywall_response(is_oa=True, pdf_url="https://example.com/paper.pdf"):
    return {
        "doi": "10.1234/test",
        "is_oa": is_oa,
        "best_oa_location": {"url_for_pdf": pdf_url, "url": pdf_url} if is_oa else None,
    }


def test_unpaywall_returns_pdf_url():
    mock_response = MagicMock()
    mock_response.json.return_value = _make_unpaywall_response()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as MockClient, \
         patch.dict("os.environ", {"UNPAYWALL_EMAIL": "test@university.edu"}):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        from qws_researcher.sources import unpaywall as uw_mod
        result = uw_mod.get_oa_pdf_url("10.1234/test")

    assert result == "https://example.com/paper.pdf"


def test_unpaywall_returns_none_when_not_oa():
    mock_response = MagicMock()
    mock_response.json.return_value = _make_unpaywall_response(is_oa=False)
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as MockClient, \
         patch.dict("os.environ", {"UNPAYWALL_EMAIL": "test@university.edu"}):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        from qws_researcher.sources import unpaywall as uw_mod
        result = uw_mod.get_oa_pdf_url("10.1234/test")

    assert result is None


def test_unpaywall_returns_none_without_email():
    with patch.dict("os.environ", {}, clear=True):
        from qws_researcher.sources import unpaywall as uw_mod
        result = uw_mod.get_oa_pdf_url("10.1234/test")

    assert result is None


def test_unpaywall_returns_none_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.Client") as MockClient, \
         patch.dict("os.environ", {"UNPAYWALL_EMAIL": "test@university.edu"}):
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response

        from qws_researcher.sources import unpaywall as uw_mod
        result = uw_mod.get_oa_pdf_url("10.1234/nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# ingest_pdf
# ---------------------------------------------------------------------------

def test_ingest_pdf_new_paper(tmp_path):
    """Ingesting a PDF with no existing library record creates a new Paper."""
    import asyncio

    pdf_file = tmp_path / "test_paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")

    with patch("papers.server._get_library") as mock_lib_fn, \
         patch("papers.extract.extract_text", return_value="Extracted full text."), \
         patch("shutil.copy2"):

        mock_lib = MagicMock()
        mock_lib.get.return_value = None  # Not in library yet
        mock_lib.add.return_value = True
        mock_lib_fn.return_value = mock_lib

        from qws_researcher.server import ingest_pdf
        result = asyncio.run(ingest_pdf(
            file_path=str(pdf_file),
            paper_id="s2:abc123",
            title="Test Paper Title",
            authors=["Author One"],
        ))

    assert result["id"] == "s2:abc123"
    assert result["title"] == "Test Paper Title"
    assert result["full_text"] == "Extracted full text."
    mock_lib.add.assert_called_once()


def test_ingest_pdf_updates_existing(tmp_path):
    """Ingesting a PDF when paper_id already exists updates the record."""
    import asyncio

    pdf_file = tmp_path / "test_paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")

    existing = Paper(
        id="s2:abc123",
        title="Existing Title from S2",
        authors=["Author One"],
        abstract="Existing abstract.",
        source="semantic_scholar",
        url="https://semanticscholar.org/paper/abc123",
        doi="10.1234/test",
    )

    with patch("papers.server._get_library") as mock_lib_fn, \
         patch("papers.extract.extract_text", return_value="Full text from PDF."), \
         patch("shutil.copy2"):

        mock_lib = MagicMock()
        mock_lib.get.return_value = existing
        mock_lib.add.return_value = False  # Already exists
        mock_lib_fn.return_value = mock_lib

        from qws_researcher.server import ingest_pdf
        result = asyncio.run(ingest_pdf(
            file_path=str(pdf_file),
            paper_id="s2:abc123",
        ))

    assert result["id"] == "s2:abc123"
    assert result["title"] == "Existing Title from S2"   # S2 metadata preserved
    assert result["abstract"] == "Existing abstract."     # S2 metadata preserved
    assert result["full_text"] == "Full text from PDF."  # PDF text added
    mock_lib.update.assert_called_once()


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_server_dedup_by_title():
    from qws_researcher.server import _dedup_by_title

    papers_input = [
        Paper(id="arxiv:1", title="Realized Volatility HAR Model", authors=[], abstract="", source="arxiv", url=""),
        Paper(id="arxiv:2", title="Realized Volatility HAR Model", authors=[], abstract="", source="arxiv", url=""),
        Paper(id="arxiv:3", title="Completely Different Paper", authors=[], abstract="", source="arxiv", url=""),
    ]

    unique = _dedup_by_title(papers_input)
    assert len(unique) == 2
    ids = [p.id for p in unique]
    assert "arxiv:1" in ids
    assert "arxiv:3" in ids
    assert "arxiv:2" not in ids


# ---------------------------------------------------------------------------
# ingest_folder
# ---------------------------------------------------------------------------

def test_ingest_folder_matches_by_doi(tmp_path):
    """PDF with valid DOI filename, DOI in library → ingested and text extracted."""
    inbox = tmp_path / "inbox"
    ingested = tmp_path / "ingested"
    unmatched = tmp_path / "unmatched"
    inbox.mkdir()

    pdf_file = inbox / "10.1016_j.najef.2026.102605.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    existing = Paper(
        id="s2:abc123",
        title="Volatility Paper",
        authors=["Author One"],
        abstract="Abstract.",
        source="semantic_scholar",
        url="https://semanticscholar.org/paper/abc123",
        doi="10.1016/j.najef.2026.102605",
    )

    with patch("papers.ingest.PaperLibrary") as MockLib, \
         patch("papers.ingest.extract_text", return_value="Extracted text."), \
         patch("shutil.copy2"), \
         patch("shutil.move"):

        mock_lib = MockLib.return_value
        mock_lib.find_by_doi.return_value = existing

        from qws_researcher.ingest import ingest_folder
        result = ingest_folder(
            inbox=str(inbox),
            ingested_dir=str(ingested),
            unmatched_dir=str(unmatched),
            data_dir=str(tmp_path / "data"),
        )

    assert len(result["ingested"]) == 1
    assert result["ingested"][0]["paper_id"] == "s2:abc123"
    assert len(result["unmatched"]) == 0
    assert len(result["errors"]) == 0
    mock_lib.update.assert_called_once()


def test_ingest_folder_unmatched_doi_not_in_library(tmp_path):
    """PDF with valid DOI filename but DOI not in library → moved to unmatched."""
    inbox = tmp_path / "inbox"
    ingested = tmp_path / "ingested"
    unmatched = tmp_path / "unmatched"
    inbox.mkdir()

    pdf_file = inbox / "10.1111_jofi.13234.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    with patch("papers.ingest.PaperLibrary") as MockLib, \
         patch("shutil.move"):

        mock_lib = MockLib.return_value
        mock_lib.find_by_doi.return_value = None  # Not in library

        from qws_researcher.ingest import ingest_folder
        result = ingest_folder(
            inbox=str(inbox),
            ingested_dir=str(ingested),
            unmatched_dir=str(unmatched),
            data_dir=str(tmp_path / "data"),
        )

    assert len(result["unmatched"]) == 1
    assert "not in library" in result["unmatched"][0]["reason"]
    assert len(result["ingested"]) == 0


def test_ingest_folder_invalid_filename(tmp_path):
    """Non-DOI filename → moved to unmatched."""
    inbox = tmp_path / "inbox"
    ingested = tmp_path / "ingested"
    unmatched = tmp_path / "unmatched"
    inbox.mkdir()

    pdf_file = inbox / "some_random_paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    with patch("papers.ingest.PaperLibrary"), \
         patch("shutil.move"):

        from qws_researcher.ingest import ingest_folder
        result = ingest_folder(
            inbox=str(inbox),
            ingested_dir=str(ingested),
            unmatched_dir=str(unmatched),
            data_dir=str(tmp_path / "data"),
        )

    assert len(result["unmatched"]) == 1
    assert result["unmatched"][0]["reason"] == "non-DOI filename"
    assert len(result["ingested"]) == 0


# ---------------------------------------------------------------------------
# CampusList
# ---------------------------------------------------------------------------

def _make_campus_entry(paper_id="s2:abc123", doi="10.1016/j.test.2026.001") -> CampusEntry:
    from qws_researcher.store.campus_list import CampusEntry
    return CampusEntry(
        paper_id=paper_id,
        title="Test Paper",
        authors=["Author One"],
        year=2026,
        doi=doi,
        filename_hint=doi.replace("/", "_") + ".pdf" if doi else None,
        source="semantic_scholar",
        url="https://semanticscholar.org/paper/abc123",
        abstract="An abstract.",
        tags=["to-read", "volatility"],
        added_at="2026-03-28T00:00:00+00:00",
        reason="Need for HAR implementation",
    )


def test_bookmark_adds_to_campus_list(tmp_path):
    """bookmark_paper with no full text should add paper to campus list."""
    import asyncio

    existing = Paper(
        id="s2:abc123",
        title="Test Paper",
        authors=["Author One"],
        abstract="Abstract.",
        source="semantic_scholar",
        url="https://semanticscholar.org/paper/abc123",
        doi="10.1016/j.test.2026.001",
    )

    with patch("papers.server._get_library") as mock_lib_fn, \
         patch("papers.server._get_campus_list") as mock_cl_fn:

        mock_lib = MagicMock()
        mock_lib.get.return_value = existing
        mock_lib_fn.return_value = mock_lib

        mock_campus = MagicMock()
        mock_campus.add.return_value = True
        mock_cl_fn.return_value = mock_campus

        from qws_researcher.server import bookmark_paper
        result = asyncio.run(bookmark_paper(
            paper_id="s2:abc123",
            reason="Need for HAR implementation",
            tags=["to-read"],
        ))

    assert result["campus_trip_needed"] is True
    assert result["filename_hint"] == "10.1016_j.test.2026.001.pdf"
    mock_campus.add.assert_called_once()


def test_bookmark_skips_campus_if_full_text(tmp_path):
    """bookmark_paper with full text should NOT add to campus list."""
    import asyncio

    existing = Paper(
        id="arxiv:2301.00001",
        title="Open Access Paper",
        authors=["Author One"],
        abstract="Abstract.",
        source="arxiv",
        url="https://arxiv.org/abs/2301.00001",
        full_text="This paper is fully available.",
    )

    with patch("papers.server._get_library") as mock_lib_fn, \
         patch("papers.server._get_campus_list") as mock_cl_fn:

        mock_lib = MagicMock()
        mock_lib.get.return_value = existing
        mock_lib_fn.return_value = mock_lib

        mock_campus = MagicMock()
        mock_cl_fn.return_value = mock_campus

        from qws_researcher.server import bookmark_paper
        result = asyncio.run(bookmark_paper(paper_id="arxiv:2301.00001"))

    assert result["campus_trip_needed"] is False
    mock_campus.add.assert_not_called()


def test_ingest_clears_campus_list(tmp_path):
    """CampusList.clear_ingested removes papers that have been ingested."""
    from qws_researcher.store.campus_list import CampusList

    cl = CampusList(data_dir=str(tmp_path))
    cl.add(_make_campus_entry("s2:abc123", doi="10.1016/j.test.2026.001"))
    cl.add(_make_campus_entry("s2:def456", doi="10.1016/j.other.2026.002"))

    assert len(cl.list_all()) == 2
    removed = cl.clear_ingested(["s2:abc123"])
    assert removed == 1
    remaining = [e.paper_id for e in cl.list_all()]
    assert "s2:abc123" not in remaining
    assert "s2:def456" in remaining


def test_campus_list_deduplicates(tmp_path):
    """Adding the same paper_id twice should return False the second time."""
    from qws_researcher.store.campus_list import CampusList

    cl = CampusList(data_dir=str(tmp_path))
    entry = _make_campus_entry()

    assert cl.add(entry) is True
    assert cl.add(entry) is False  # duplicate
    assert len(cl.list_all()) == 1


# ---------------------------------------------------------------------------
# Title safety + StandardSearchResult
# ---------------------------------------------------------------------------

def _make_paper(**kwargs) -> Paper:
    defaults = dict(
        id="arxiv:2301.00001",
        title="A Fine Paper",
        authors=["Jane Smith"],
        abstract="Abstract text.",
        source="arxiv",
        url="https://arxiv.org/abs/2301.00001",
    )
    defaults.update(kwargs)
    return Paper(**defaults)


def test_paper_summary_never_shows_url_as_title():
    from qws_researcher import PaperSummary

    p_none = _make_paper(title=None)
    p_url = _make_paper(title="https://example.com/paper")

    s_none = PaperSummary.from_paper(p_none)
    s_url = PaperSummary.from_paper(p_url)

    assert s_none.title == "[No title — re-fetch arxiv:2301.00001]"
    assert s_url.title == "[No title — re-fetch arxiv:2301.00001]"
    assert not s_none.title.startswith("http")
    assert not s_url.title.startswith("http")


def test_standard_result_truncates_long_title():
    from qws_researcher import StandardSearchResult

    long_title = "A" * 70
    p = _make_paper(title=long_title)
    r = StandardSearchResult.from_paper(p, 1)

    assert r.title.endswith("…")
    assert len(r.title) == 61  # 60 chars + ellipsis character


def test_standard_result_formats_citations():
    from qws_researcher import StandardSearchResult

    assert StandardSearchResult.from_paper(_make_paper(citations=1234), 1).citations == "1,234"
    assert StandardSearchResult.from_paper(_make_paper(citations=None), 1).citations == "—"
    assert StandardSearchResult.from_paper(_make_paper(citations=0), 1).citations == "—"


def test_standard_result_shortens_source():
    from qws_researcher import StandardSearchResult

    p = _make_paper(source="semantic_scholar")
    r = StandardSearchResult.from_paper(p, 1)
    assert r.source == "s2"


def test_standard_result_formats_authors():
    from qws_researcher import StandardSearchResult

    authors = ["John Smith", "Jane Doe", "Alice Brown", "Bob Jones"]
    p = _make_paper(authors=authors)
    r = StandardSearchResult.from_paper(p, 1)

    assert r.authors == "Smith, J.; Doe, J.; Brown, A.; et al."


def test_standard_result_never_url_title():
    from qws_researcher import StandardSearchResult

    p = _make_paper(title="https://example.com/paper.pdf")
    r = StandardSearchResult.from_paper(p, 1)

    assert r.title == "[No title — re-fetch arxiv:2301.00001]"
    assert not r.title.startswith("http")


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def _crossref_response(doi: str, score: float) -> dict:
    return {
        "message": {
            "items": [{"DOI": doi, "title": ["Some Paper Title"], "score": score}]
        }
    }


def test_crossref_returns_doi_on_high_score():
    from qws_researcher.sources import crossref as crossref_src

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _crossref_response("10.1016/j.jfineco.2020.01.001", score=85.0)

    with patch("papers.sources.crossref.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        doi = crossref_src.lookup_doi("HAR Model for Realized Volatility", "Corsi")

    assert doi == "10.1016/j.jfineco.2020.01.001"


def test_crossref_returns_none_on_low_score():
    from qws_researcher.sources import crossref as crossref_src

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _crossref_response("10.1016/j.jfineco.2020.01.001", score=20.0)

    with patch("papers.sources.crossref.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        doi = crossref_src.lookup_doi("some vague title")

    assert doi is None


def test_crossref_returns_none_on_empty_results():
    from qws_researcher.sources import crossref as crossref_src

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"items": []}}

    with patch("papers.sources.crossref.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        doi = crossref_src.lookup_doi("Nonexistent paper title nobody wrote")

    assert doi is None


def test_crossref_returns_none_on_http_error():
    from qws_researcher.sources import crossref as crossref_src

    mock_resp = MagicMock()
    mock_resp.status_code = 503

    with patch("papers.sources.crossref.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        doi = crossref_src.lookup_doi("Any Title")

    assert doi is None


def test_crossref_returns_none_on_empty_title():
    from qws_researcher.sources import crossref as crossref_src

    assert crossref_src.lookup_doi("") is None
    assert crossref_src.lookup_doi(None) is None


# ---------------------------------------------------------------------------
# add_repo tool
# ---------------------------------------------------------------------------

def test_add_repo_links_repo(tmp_path):
    import asyncio
    from unittest.mock import MagicMock, patch

    paper = Paper(
        id="arxiv:2301.00001",
        title="HAR Model",
        authors=["Corsi, F."],
        abstract="abstract",
        source="arxiv",
        url="https://arxiv.org/abs/2301.00001",
        fetched_at="2026-03-28T00:00:00",
    )

    mock_lib = MagicMock()
    mock_lib.get.return_value = paper

    async def run():
        with patch("papers.server._get_library", return_value=mock_lib):
            from qws_researcher.server import add_repo
            result = await add_repo("arxiv:2301.00001", "turboPutty/rBergomi")
        return result

    result = asyncio.run(run())
    assert "turboPutty/rBergomi" in result
    assert "turboPutty/rBergomi" in paper.github_repos
    mock_lib.update.assert_called_once_with(paper)


def test_add_repo_deduplicates(tmp_path):
    import asyncio
    from unittest.mock import MagicMock, patch

    paper = Paper(
        id="arxiv:2301.00001",
        title="HAR Model",
        authors=["Corsi, F."],
        abstract="abstract",
        source="arxiv",
        url="https://arxiv.org/abs/2301.00001",
        fetched_at="2026-03-28T00:00:00",
        github_repos=["turboPutty/rBergomi"],
    )

    mock_lib = MagicMock()
    mock_lib.get.return_value = paper

    async def run():
        with patch("papers.server._get_library", return_value=mock_lib):
            from qws_researcher.server import add_repo
            await add_repo("arxiv:2301.00001", "turboPutty/rBergomi")

    asyncio.run(run())
    assert paper.github_repos.count("turboPutty/rBergomi") == 1
    mock_lib.update.assert_not_called()
