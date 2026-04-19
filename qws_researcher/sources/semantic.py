from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from semanticscholar import SemanticScholar

from qws_researcher import Paper, id_safe

logger = logging.getLogger(__name__)

FIELDS_OF_STUDY = ["Finance", "Economics", "Mathematics", "Statistics", "Physics"]

_PAPER_FIELDS = [
    "title",
    "authors",
    "abstract",
    "year",
    "citationCount",
    "openAccessPdf",
    "references",
    "externalIds",
    "url",
    "fieldsOfStudy",
    "publicationDate",
]

_BULK_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
_BULK_FIELDS = (
    "paperId,externalIds,title,authors,abstract,year,citationCount,openAccessPdf,fieldsOfStudy"
)

# Only attempt PDF download from these trusted open-access hosts
_OA_TRUSTED_HOSTS = {"arxiv.org", "ar5iv.labs.arxiv.org", "export.arxiv.org"}


def _get_client() -> SemanticScholar:
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    return SemanticScholar(api_key=api_key if api_key else None)


def _build_headers() -> dict:
    headers = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _bulk_result_to_paper(item: dict, data_dir: str = "data") -> Paper | None:
    """Convert a bulk search API dict to Paper. Returns None on bad data."""
    try:
        title = item.get("title") or ""
        if not title or title.startswith("http"):
            return None

        abstract = item.get("abstract") or ""
        authors = [a["name"] for a in (item.get("authors") or []) if a.get("name")]

        s2_id = item.get("paperId") or ""
        ext_ids = item.get("externalIds") or {}

        if "ArXiv" in ext_ids:
            paper_id = f"arxiv:{ext_ids['ArXiv']}"
            url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
        elif "SSRN" in ext_ids:
            paper_id = f"ssrn:{ext_ids['SSRN']}"
            url = f"https://papers.ssrn.com/abstract={ext_ids['SSRN']}"
        else:
            paper_id = f"s2:{s2_id}"
            url = f"https://www.semanticscholar.org/paper/{s2_id}"

        year = item.get("year")
        pub_str = str(year) if year else None
        citations = item.get("citationCount")
        categories = item.get("fieldsOfStudy") or []

        oa_pdf = item.get("openAccessPdf") or {}
        pdf_url = oa_pdf.get("url") or "" if isinstance(oa_pdf, dict) else ""

        pdf_path = None
        if pdf_url:
            host = urlparse(pdf_url).netloc.lstrip("www.")
            if pdf_url.endswith(".pdf") or host in _OA_TRUSTED_HOSTS:
                pdf_path = f"url:{pdf_url}"

        doi = ext_ids.get("DOI")

        return Paper(
            id=paper_id,
            title=title.strip(),
            authors=authors,
            abstract=abstract.strip(),
            source="semantic_scholar",
            url=url,
            published_date=pub_str,
            categories=list(categories),
            citations=citations,
            references=[],
            pdf_path=pdf_path,
            fetched_at="",
            doi=doi,
        )

    except Exception as e:
        logger.warning("Failed to convert S2 bulk result: %s", e)
        return None


def _s2_paper_to_paper(result: object, data_dir: str = "data") -> Paper | None:
    """Convert a Semantic Scholar paper result to Paper. Returns None on bad data."""
    try:
        title = getattr(result, "title", None) or ""
        abstract = getattr(result, "abstract", None) or ""
        if not title or title.startswith("http"):
            return None

        authors = []
        for a in getattr(result, "authors", []) or []:
            name = getattr(a, "name", None)
            if name:
                authors.append(name)

        # Determine canonical ID
        ext_ids = getattr(result, "externalIds", {}) or {}
        if "ArXiv" in ext_ids:
            paper_id = f"arxiv:{ext_ids['ArXiv']}"
            url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
        elif "PubMed" in ext_ids:
            paper_id = f"pmid:{ext_ids['PubMed']}"
            url = f"https://pubmed.ncbi.nlm.nih.gov/{ext_ids['PubMed']}/"
        else:
            s2_id = getattr(result, "paperId", None) or ""
            paper_id = f"s2:{s2_id}"
            url = getattr(result, "url", None) or f"https://www.semanticscholar.org/paper/{s2_id}"

        pub_date = getattr(result, "publicationDate", None)
        pub_str = str(pub_date) if pub_date else None

        citations = getattr(result, "citationCount", None)

        refs = []
        for r in getattr(result, "references", []) or []:
            r_ids = getattr(r, "externalIds", {}) or {}
            if "ArXiv" in r_ids:
                refs.append(f"arxiv:{r_ids['ArXiv']}")
            elif r_pid := getattr(r, "paperId", None):
                refs.append(f"s2:{r_pid}")

        categories = getattr(result, "fieldsOfStudy", []) or []

        # Collect open-access PDF URL (stored as pdf_path if it's a trusted host)
        # Actual download happens in fetch_paper, not during search
        oa_pdf = getattr(result, "openAccessPdf", None)
        if oa_pdf and isinstance(oa_pdf, dict):
            pdf_url = oa_pdf.get("url") or ""
        else:
            pdf_url = getattr(oa_pdf, "url", None) or "" if oa_pdf else ""

        pdf_path = None
        if pdf_url:
            host = urlparse(pdf_url).netloc.lstrip("www.")
            if pdf_url.endswith(".pdf") or host in _OA_TRUSTED_HOSTS:
                # Store the URL as pdf_path with a URL: prefix so server.py can detect it
                pdf_path = f"url:{pdf_url}"

        return Paper(
            id=paper_id,
            title=title.strip(),
            authors=authors,
            abstract=abstract.strip(),
            source="semantic_scholar",
            url=url,
            published_date=pub_str,
            categories=list(categories),
            citations=citations,
            references=refs[:50],
            pdf_path=pdf_path,
            fetched_at="",
        )

    except Exception as e:
        logger.warning("Failed to convert S2 result: %s", e)
        return None


def download_pdf(pdf_url: str, paper_id: str, data_dir: str) -> str | None:
    """Download a PDF from a URL to local storage. Silent failure."""
    try:
        papers_dir = Path(data_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = papers_dir / f"{id_safe(paper_id)}.pdf"
        if pdf_path.exists():
            return str(pdf_path)

        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()
            content = resp.content
            if not content[:4] == b"%PDF":
                return None
            pdf_path.write_bytes(content)
        return str(pdf_path)

    except Exception as e:
        logger.warning("S2 PDF download failed for %s: %s", paper_id, e)
        return None


def search(
    query: str,
    fields_of_study: list[str] | None = None,
    max_results: int = 20,
    data_dir: str = "data",
) -> list[Paper]:
    """Search Semantic Scholar for papers using the bulk search endpoint."""
    try:
        fos = fields_of_study or FIELDS_OF_STUDY
        params = {
            "query": query,
            "fields": _BULK_FIELDS,
            "fieldsOfStudy": ",".join(fos),
            "limit": min(max_results, 1000),
        }

        time.sleep(1.1)
        with httpx.Client(timeout=30) as client:
            resp = client.get(_BULK_SEARCH_URL, params=params, headers=_build_headers())
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for item in data.get("data") or []:
            paper = _bulk_result_to_paper(item, data_dir)
            if paper:
                papers.append(paper)
            if len(papers) >= max_results:
                break

        return papers

    except Exception as e:
        logger.warning("Semantic Scholar bulk search failed: %s", e)
        return []


def get_doi(paper_id: str) -> str | None:
    """Fetch the DOI for a paper directly from S2's paper endpoint."""
    try:
        s2_id = paper_id.removeprefix("s2:")
        time.sleep(1.1)
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}",
                params={"fields": "externalIds"},
                headers=_build_headers(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
        return (data.get("externalIds") or {}).get("DOI")
    except Exception as e:
        logger.warning("S2 DOI lookup failed for %s: %s", paper_id, e)
        return None


def get_recommendations(paper_id: str, limit: int = 10, data_dir: str = "data") -> list[Paper]:
    """Get paper recommendations from Semantic Scholar."""
    try:
        sch = _get_client()
        s2_id = _resolve_s2_id(sch, paper_id)
        if not s2_id:
            return []

        time.sleep(1.1)
        results = sch.get_recommended_papers(s2_id, fields=_PAPER_FIELDS, limit=limit)
        papers = []
        for result in results:
            paper = _s2_paper_to_paper(result, data_dir)
            if paper:
                papers.append(paper)
        return papers

    except Exception as e:
        logger.warning("S2 recommendations failed for %s: %s", paper_id, e)
        return []


def get_citations(paper_id: str, limit: int = 50, data_dir: str = "data") -> list[Paper]:
    """Get papers that cite the given paper."""
    try:
        sch = _get_client()
        s2_id = _resolve_s2_id(sch, paper_id)
        if not s2_id:
            return []

        time.sleep(1.1)
        results = sch.get_paper_citations(s2_id, fields=_PAPER_FIELDS, limit=limit)
        papers = []
        for cit in results:
            result = getattr(cit, "citingPaper", cit)
            paper = _s2_paper_to_paper(result, data_dir)
            if paper:
                papers.append(paper)
        return papers

    except Exception as e:
        logger.warning("S2 citations failed for %s: %s", paper_id, e)
        return []


def get_references(paper_id: str, limit: int = 50, data_dir: str = "data") -> list[Paper]:
    """Get papers referenced by the given paper."""
    try:
        sch = _get_client()
        s2_id = _resolve_s2_id(sch, paper_id)
        if not s2_id:
            return []

        time.sleep(1.1)
        results = sch.get_paper_references(s2_id, fields=_PAPER_FIELDS, limit=limit)
        papers = []
        for ref in results:
            result = getattr(ref, "citedPaper", ref)
            paper = _s2_paper_to_paper(result, data_dir)
            if paper:
                papers.append(paper)
        return papers

    except Exception as e:
        logger.warning("S2 references failed for %s: %s", paper_id, e)
        return []


def get_paper_by_doi(doi: str, data_dir: str = "data") -> Paper | None:
    """Fetch a single paper by DOI using S2's direct paper endpoint (not bulk search)."""
    try:
        sch = _get_client()
        time.sleep(1.1)
        result = sch.get_paper(f"DOI:{doi}", fields=_PAPER_FIELDS)
        if result is None:
            return None
        paper = _s2_paper_to_paper(result, data_dir)
        if paper and not paper.doi:
            paper.doi = doi
        return paper
    except Exception as e:
        logger.warning("S2 DOI lookup failed for %s: %s", doi, e)
        return None


def _resolve_s2_id(sch: SemanticScholar, paper_id: str) -> str | None:
    """Resolve our internal paper ID to a Semantic Scholar paper ID."""
    try:
        time.sleep(1.1)
        if paper_id.startswith("arxiv:"):
            arxiv_id = paper_id.removeprefix("arxiv:")
            result = sch.get_paper(f"ArXiv:{arxiv_id}", fields=["paperId"])
            return result.paperId if result else None
        elif paper_id.startswith("pmid:"):
            pmid = paper_id.removeprefix("pmid:")
            result = sch.get_paper(f"PMID:{pmid}", fields=["paperId"])
            return result.paperId if result else None
        elif paper_id.startswith("s2:"):
            return paper_id.removeprefix("s2:")
        else:
            return None
    except Exception as e:
        logger.warning("Could not resolve S2 ID for %s: %s", paper_id, e)
        return None
