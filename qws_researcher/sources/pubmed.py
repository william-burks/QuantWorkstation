from __future__ import annotations

import logging
import os
from xml.etree import ElementTree

from Bio import Entrez

from qws_researcher import Paper

logger = logging.getLogger(__name__)

_QUANT_FILTER = (
    'AND (econophysics OR "complex systems" OR "statistical mechanics" OR "agent-based")'
)


def _set_email() -> None:
    email = os.environ.get("PUBMED_EMAIL", "researcher@example.com")
    Entrez.email = email


def search(query: str, max_results: int = 20) -> list[Paper]:
    """Search PubMed with an automatic quant-finance relevance filter."""
    _set_email()
    try:
        full_query = f"({query}) {_QUANT_FILTER}"
        handle = Entrez.esearch(db="pubmed", term=full_query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()

        ids = record.get("IdList", [])
        if not ids:
            return []

        papers = []
        for pmid in ids:
            abstract = fetch_abstract(pmid)
            if abstract is None:
                continue
            papers.append(abstract)

        return papers

    except Exception as e:
        logger.warning("PubMed search failed: %s", e)
        return []


def fetch_abstract(pmid: str) -> Paper | None:
    """Fetch metadata and abstract for a single PubMed ID."""
    _set_email()
    try:
        handle = Entrez.efetch(db="pubmed", id=pmid, rettype="xml", retmode="xml")
        xml_data = handle.read()
        handle.close()

        root = ElementTree.fromstring(xml_data)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        # Title
        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        # Abstract
        abstract_parts = []
        for abstract_el in article.findall(".//AbstractText"):
            label = abstract_el.get("Label")
            text = "".join(abstract_el.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        # Authors
        authors = []
        for author_el in article.findall(".//Author"):
            last = author_el.findtext("LastName", "")
            fore = author_el.findtext("ForeName", "")
            if last:
                authors.append(f"{fore} {last}".strip())

        # Date
        pub_date_el = article.find(".//PubDate")
        pub_date = None
        if pub_date_el is not None:
            year = pub_date_el.findtext("Year", "")
            month = pub_date_el.findtext("Month", "01")
            if year:
                pub_date = f"{year}-{month}"

        # MeSH terms as categories
        categories = []
        for mesh_el in article.findall(".//MeshHeading/DescriptorName"):
            categories.append(mesh_el.text or "")

        return Paper(
            id=f"pmid:{pmid}",
            title=title,
            authors=authors,
            abstract=abstract,
            source="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published_date=pub_date,
            categories=categories,
            citations=None,
            references=[],
            fetched_at="",
        )

    except Exception as e:
        logger.warning("PubMed fetch failed for pmid:%s: %s", pmid, e)
        return None
