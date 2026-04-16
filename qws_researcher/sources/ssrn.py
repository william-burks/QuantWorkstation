from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from qws_researcher import Paper, id_safe

logger = logging.getLogger(__name__)


def _extract_ssrn_id(url: str) -> str | None:
    """Extract SSRN paper ID from URL."""
    match = re.search(r"(?:abstract=|ssrn\.com/abstract/)(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"/(\d{6,})", url)
    if match:
        return match.group(1)
    return None


def _parse_html(html: str, url: str) -> dict:
    """Parse SSRN abstract page HTML for metadata using basic string operations."""
    data: dict = {"title": "", "authors": [], "abstract": "", "date": None}

    # Title: <meta name="citation_title" content="...">
    m = re.search(r'<meta\s+name=["\']citation_title["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if m:
        data["title"] = m.group(1).strip()

    if not data["title"]:
        m = re.search(r'<h1[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if m:
            data["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # Authors: <meta name="citation_author" content="..."> (multiple)
    authors = re.findall(r'<meta\s+name=["\']citation_author["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    data["authors"] = [a.strip() for a in authors if a.strip()]

    # Abstract
    m = re.search(r'<div[^>]+class=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</div>', html, re.IGNORECASE | re.DOTALL)
    if m:
        data["abstract"] = re.sub(r"<[^>]+>", " ", m.group(1)).strip()

    if not data["abstract"]:
        m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if m:
            data["abstract"] = m.group(1).strip()

    # Date
    m = re.search(r'<meta\s+name=["\']citation_publication_date["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if m:
        data["date"] = m.group(1).strip()

    if not data["date"]:
        m = re.search(r"Posted:?\s+(\w+\s+\d{1,2},?\s+\d{4})", html)
        if m:
            data["date"] = m.group(1).strip()

    return data


def fetch_by_url(url: str, data_dir: str = "data") -> Paper:
    """
    Fetch an SSRN paper by URL. Returns metadata + abstract.
    PDF download is attempted but failure is silent — paper is stored with
    full_text=None and pdf_path=None if PDF is unavailable.
    """
    ssrn_id = _extract_ssrn_id(url)
    if not ssrn_id:
        # Fallback ID from URL hash
        ssrn_id = str(abs(hash(url)) % 10**8)

    paper_id = f"ssrn:{ssrn_id}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; academic-research-bot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }
        with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code == 403 or "Enable JavaScript and cookies" in resp.text:
                raise RuntimeError(
                    "SSRN is protected by Cloudflare and cannot be accessed programmatically. "
                    "Open the URL in a browser to read the paper."
                )
            resp.raise_for_status()
            html = resp.text
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("SSRN page fetch failed for %s: %s", url, e)
        return Paper(
            id=paper_id,
            title=url,
            authors=[],
            abstract="",
            source="ssrn",
            url=url,
            fetched_at="",
        )

    parsed = _parse_html(html, url)

    # Attempt PDF download silently
    pdf_path = None
    pdf_url = f"https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID{ssrn_id}_code.pdf"
    try:
        papers_dir = Path(data_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        dest = papers_dir / f"{id_safe(paper_id)}.pdf"

        if not dest.exists():
            headers_pdf = {
                "User-Agent": "Mozilla/5.0 (compatible; academic-research-bot/1.0)",
            }
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers_pdf) as client:
                resp = client.get(pdf_url)
                if resp.status_code == 200 and b"%PDF" in resp.content[:10]:
                    dest.write_bytes(resp.content)
                    pdf_path = str(dest)
        else:
            pdf_path = str(dest)

    except Exception:
        pass  # Silent PDF failure per spec

    return Paper(
        id=paper_id,
        title=parsed["title"] or url,
        authors=parsed["authors"],
        abstract=parsed["abstract"],
        source="ssrn",
        url=url,
        published_date=parsed["date"],
        categories=["Finance"],
        pdf_path=pdf_path,
        fetched_at="",
    )
