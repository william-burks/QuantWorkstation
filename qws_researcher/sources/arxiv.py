from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import arxiv
import httpx

from qws_researcher import Paper, id_safe

logger = logging.getLogger(__name__)

SUPPORTED_CATEGORIES = [
    "q-fin.TR",
    "q-fin.PM",
    "q-fin.RM",
    "q-fin.MF",
    "q-fin.ST",
    "q-fin.CP",
    "stat.ML",
    "stat.AP",
    "physics.data-an",
    "cond-mat.stat-mech",
]

_ATOM_NS = "http://www.w3.org/2005/Atom"
_SEARCH_URL = "https://export.arxiv.org/api/query"
# Generic browser UA avoids the per-UA rate limit applied to arxiv.py/x.y.z
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-tool/1.0)"}

# arXiv enforces ~1 request per 3 seconds. Use 4s to stay clear.
_MIN_INTERVAL = 4.0
_lock = threading.Lock()
_last_request: float = 0.0

# Keep arxiv client only for PDF downloads (id_list endpoint, different quota).
_client = arxiv.Client(delay_seconds=3, num_retries=3)


def _throttle() -> None:
    """Block until safe to make the next arXiv API request."""
    global _last_request
    with _lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _parse_atom(xml_bytes: bytes) -> list[Paper]:
    """Parse arXiv Atom feed XML into Paper objects."""
    root = ET.fromstring(xml_bytes)
    papers = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        raw_id = (entry.findtext(f"{{{_ATOM_NS}}}id") or "").strip()
        # e.g. "http://arxiv.org/abs/1410.3394v2" → "1410.3394"
        arxiv_id = raw_id.split("/abs/")[-1].split("v")[0]
        if not arxiv_id:
            continue
        paper_id = f"arxiv:{arxiv_id}"

        title = (entry.findtext(f"{{{_ATOM_NS}}}title") or "").strip().replace("\n", " ")
        abstract = (entry.findtext(f"{{{_ATOM_NS}}}summary") or "").strip()
        published = (entry.findtext(f"{{{_ATOM_NS}}}published") or "")[:10]  # "YYYY-MM-DD"

        authors = [
            (a.findtext(f"{{{_ATOM_NS}}}name") or "").strip()
            for a in entry.findall(f"{{{_ATOM_NS}}}author")
        ]

        categories = [
            c.get("term", "")
            for c in entry.findall("{http://arxiv.org/schemas/atom}primary_category")
            + entry.findall(f"{{{_ATOM_NS}}}category")
        ]
        categories = [c for c in categories if c]

        # PDF link: <link type="application/pdf" href="..."/>
        pdf_url = None
        for link in entry.findall(f"{{{_ATOM_NS}}}link"):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href")
                break
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        papers.append(
            Paper(
                id=paper_id,
                title=title,
                authors=authors,
                abstract=abstract,
                source="arxiv",
                url=f"https://arxiv.org/abs/{arxiv_id}",
                published_date=published or None,
                categories=categories,
                citations=None,
                references=[],
                fetched_at="",
                pdf_path=f"url:{pdf_url}",
            )
        )
    return papers


def search(
    query: str,
    categories: list[str] | None = None,
    max_results: int = 20,
    data_dir: str = "data",
) -> list[Paper]:
    """Search arXiv using the Atom API directly (avoids library UA rate-limit)."""
    full_query = query
    if categories:
        valid_cats = [c for c in categories if c in SUPPORTED_CATEGORIES]
        if valid_cats:
            cat_filter = " OR ".join(f"cat:{c}" for c in valid_cats)
            full_query = f"({query}) AND ({cat_filter})"

    params = {
        "search_query": full_query,
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    for attempt in range(2):
        try:
            _throttle()
            with httpx.Client(timeout=30, headers=_HEADERS) as client:
                resp = client.get(_SEARCH_URL, params=params)
                if resp.status_code == 429:
                    if attempt == 0:
                        logger.warning("arXiv rate limited (429), backing off 30s before retry")
                        time.sleep(30)
                        continue
                    logger.warning("arXiv rate limited (429) after retry, giving up")
                    return []
                resp.raise_for_status()
                return _parse_atom(resp.content)
        except httpx.HTTPError as e:
            logger.warning("arXiv search HTTP error: %s", e)
            return []
        except Exception as e:
            logger.warning("arXiv search failed: %s", e)
            return []

    return []


def fetch_arxiv_source(arxiv_path: str) -> str | None:
    """
    Download arXiv .tex source. Returns concatenated .tex content or None.

    arxiv_path is the raw arXiv path — no 'arxiv:' prefix. Accepts both modern
    IDs ('2301.00001') and old-format category-prefixed IDs ('math/0006100').
    Caller is responsible for extracting the correct path from paper.url when
    needed (old-format papers store the category in the URL, not the paper_id).

    Hits https://arxiv.org/e-print/{arxiv_path} which serves .tar.gz for most
    papers or a bare .tex file for very old submissions.
    """
    import io
    import tarfile

    url = f"https://arxiv.org/e-print/{arxiv_path}"

    _throttle()
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            raw = resp.content
    except Exception as e:
        logger.warning("arXiv source fetch failed for %s: %s", arxiv_path, e)
        return None

    # Try tar.gz first (most submissions)
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            tex_members = [m for m in tar.getmembers() if m.name.endswith(".tex")]
            if not tex_members:
                return None
            tex_members.sort(key=lambda m: m.size, reverse=True)
            parts = []
            for member in tex_members[:3]:
                f = tar.extractfile(member)
                if f:
                    try:
                        parts.append(f.read().decode("utf-8", errors="replace"))
                    except Exception:
                        pass
            return "\n\n%%% NEXT FILE %%%\n\n".join(parts) if parts else None
    except tarfile.TarError:
        pass

    # Older submissions are a bare .tex file (not compressed)
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("arXiv source decode failed for %s: %s", arxiv_path, e)
        return None


def fetch_pdf(paper_id: str, data_dir: str = "data") -> str | None:
    """Download arXiv PDF to local storage. Returns path or None on failure."""
    try:
        arxiv_id = paper_id.removeprefix("arxiv:")
        papers_dir = Path(data_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = papers_dir / f"{id_safe(paper_id)}.pdf"
        if pdf_path.exists():
            return str(pdf_path)

        result = next(_client.results(arxiv.Search(id_list=[arxiv_id])))
        result.download_pdf(dirpath=str(papers_dir), filename=f"{id_safe(paper_id)}.pdf")
        return str(pdf_path)

    except Exception as e:
        logger.warning("arXiv PDF fetch failed for %s: %s", paper_id, e)
        return None
