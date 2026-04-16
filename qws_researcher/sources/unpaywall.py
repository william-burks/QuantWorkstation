from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from qws_researcher import id_safe

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.unpaywall.org/v2"


def get_oa_pdf_url(doi: str) -> str | None:
    """
    Query Unpaywall for an open-access PDF URL given a DOI.
    Requires UNPAYWALL_EMAIL env var. Returns None if not OA or on any error.
    """
    email = os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        logger.debug("UNPAYWALL_EMAIL not set, skipping Unpaywall lookup")
        return None

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{_BASE_URL}/{doi}", params={"email": email})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

        if not data.get("is_oa"):
            return None

        best = data.get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url") or None

    except Exception as e:
        logger.warning("Unpaywall lookup failed for DOI %s: %s", doi, e)
        return None


def download_pdf(pdf_url: str, paper_id: str, data_dir: str) -> str | None:
    """Download a PDF from an Unpaywall OA URL. Returns local path or None."""
    try:
        papers_dir = Path(data_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        dest = papers_dir / f"{id_safe(paper_id)}.pdf"

        if dest.exists():
            return str(dest)

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()
            if b"%PDF" not in resp.content[:10]:
                return None
            dest.write_bytes(resp.content)

        return str(dest)

    except Exception as e:
        logger.warning("Unpaywall PDF download failed for %s: %s", paper_id, e)
        return None
