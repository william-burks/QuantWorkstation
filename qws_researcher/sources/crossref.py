from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org/v1/works"
_HEADERS = {"User-Agent": "research-tool/1.0 (mailto:research@example.com)"}


def lookup_doi(title: str, first_author: str | None = None) -> str | None:
    """
    Fuzzy-search Crossref by title (+optional first author) and return the best DOI match.
    Returns None if no confident match is found or on any error.
    """
    if not title or not title.strip():
        return None

    query = title.strip()
    if first_author:
        query = f"{query} {first_author.strip()}"

    try:
        with httpx.Client(timeout=15, headers=_HEADERS) as client:
            resp = client.get(_BASE_URL, params={"query": query, "rows": 1, "select": "DOI,title,score"})
            if resp.status_code != 200:
                logger.debug("Crossref returned %s for query %r", resp.status_code, query[:60])
                return None
            items = resp.json().get("message", {}).get("items", [])

        if not items:
            return None

        item = items[0]
        doi = item.get("DOI", "").strip()
        score = item.get("score", 0)

        # Crossref relevance scores above ~50 are generally reliable matches.
        # Below that threshold, the fuzzy match is too uncertain to trust.
        if score < 50:
            logger.debug("Crossref score too low (%s) for %r — skipping", score, title[:60])
            return None

        return doi or None

    except Exception as e:
        logger.warning("Crossref lookup failed for %r: %s", title[:60], e)
        return None
