from __future__ import annotations

import asyncio
import difflib
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastmcp import FastMCP

from qws_researcher import Paper, StandardSearchResult, id_safe
from qws_researcher.store.campus_list import CampusEntry, CampusList
from qws_researcher.store.library import PaperLibrary

logger = logging.getLogger(__name__)

# Shared research data directory. Override with RESEARCH_DATA_DIR env var.
# Defaults to the shared core/data/ location; tests override srv._DATA_DIR directly.
_DATA_DIR = os.path.expanduser(
    os.environ.get(
        "RESEARCH_DATA_DIR",
        os.environ.get("PAPERS_DATA_DIR", "~/ClaudeProjects/QuantResearcher/core/data"),
    )
)

_library: PaperLibrary | None = None


def _get_library() -> PaperLibrary:
    if _library is None:
        raise RuntimeError("Library not initialized")
    return _library


def _get_campus_list() -> CampusList:
    return CampusList(data_dir=_DATA_DIR)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _dedup_by_title(papers: list[Paper], threshold: float = 0.85) -> list[Paper]:
    """Remove near-duplicate papers by title similarity."""
    seen_titles: list[str] = []
    unique: list[Paper] = []

    for paper in papers:
        title_lower = paper.title.lower()
        is_dup = any(
            difflib.SequenceMatcher(None, title_lower, seen).ratio() >= threshold
            for seen in seen_titles
        )
        if not is_dup:
            seen_titles.append(title_lower)
            unique.append(paper)

    return unique


async def _run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


@asynccontextmanager
async def _lifespan(server):
    global _library
    _library = PaperLibrary(data_dir=_DATA_DIR)
    logger.info("PaperLibrary initialized at %s", _DATA_DIR)
    try:
        yield
    finally:
        _library = None


mcp = FastMCP(
    name="papers",
    instructions=(
        "Search, fetch, and store academic papers from Semantic Scholar. Papers"
        "are stored locally with full text and indexed for semantic search."
        "Use search_papers to find papers, fetch_paper to get full text,"
        "read_paper to load content into context, and find_similar to discover"
        "related work."
    ),
    lifespan=_lifespan,
)


@mcp.tool()
async def search_papers(
    query: str,
    max_per_source: int = 10,
    save: bool = True,
) -> list[dict]:
    """
    Search for academic papers across multiple sources in parallel.

    Returns a ranked, deduplicated list of papers. Optionally saves results to local library.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        query: Search query string
        sources: List of sources to search: "arxiv", "semantic_scholar", "pubmed"
        max_per_source: Maximum results per source
        save: If True, automatically save results to local library
    """
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()

    async def _search_semantic():
        return await _run_in_executor(semantic_src.search, query, None, max_per_source, _DATA_DIR)

    results = await asyncio.gather(_search_semantic())

    all_papers: list[Paper] = []
    for batch in results:
        all_papers.extend(batch)

    # Deduplicate by title similarity
    unique = _dedup_by_title(all_papers)

    # Sort by citations descending (None last)
    unique.sort(key=lambda p: p.citations or 0, reverse=True)

    if save:
        for paper in unique:
            paper.fetched_at = _now()
            lib.add(paper)

    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(unique)]


@mcp.tool()
async def fetch_paper(paper_id: str) -> dict:
    """
    Fetch a paper's full text by ID. Downloads PDF and extracts text if not cached.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001", "pmid:12345", or a URL for SSRN papers
    """
    from qws_researcher.extract import extract_text  # noqa: PLC0415
    from qws_researcher.sources import arxiv as arxiv_src  # noqa: PLC0415
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415
    from qws_researcher.sources import ssrn as ssrn_src  # noqa: PLC0415

    lib = _get_library()

    # Handle SSRN URLs passed as paper_id
    if paper_id.startswith("http") and "ssrn" in paper_id:
        paper = await _run_in_executor(ssrn_src.fetch_by_url, paper_id, _DATA_DIR)
        paper.fetched_at = _now()
        if not lib.add(paper):
            lib.update(paper)
        return paper.to_dict()

    # Check local library first
    paper = lib.get(paper_id)
    if paper and paper.full_text:
        return paper.to_dict()

    # Fetch from source
    if paper_id.startswith("arxiv:"):
        if paper is None:
            # Re-fetch metadata
            arxiv_id = paper_id.removeprefix("arxiv:")
            papers = await _run_in_executor(arxiv_src.search, f"id:{arxiv_id}", None, 1, _DATA_DIR)
            paper = papers[0] if papers else None

        if paper:
            pdf_path = await _run_in_executor(arxiv_src.fetch_pdf, paper_id, _DATA_DIR)
            if pdf_path:
                paper.pdf_path = pdf_path
                text = await _run_in_executor(extract_text, pdf_path)
                if text:
                    paper.full_text = text
                    text_path = Path(_DATA_DIR) / "text" / f"{id_safe(paper_id)}.txt"
                    text_path.parent.mkdir(parents=True, exist_ok=True)
                    text_path.write_text(text, encoding="utf-8")
                    paper.text_path = str(text_path)

    elif paper_id.startswith("s2:") or paper_id.startswith("pmid:"):
        from qws_researcher.sources import unpaywall as unpaywall_src  # noqa: PLC0415

        # Try S2 OA PDF first
        if paper and paper.pdf_path and paper.pdf_path.startswith("url:"):
            pdf_url = paper.pdf_path.removeprefix("url:")
            local_path = await _run_in_executor(
                semantic_src.download_pdf, pdf_url, paper_id, _DATA_DIR
            )
            if local_path:
                paper.pdf_path = local_path

        # Resolve DOI from S2 if not cached (handles papers stored before doi field was added)
        if paper and not paper.doi and paper_id.startswith("s2:"):
            paper.doi = await _run_in_executor(semantic_src.get_doi, paper_id)

        # Fall back to Unpaywall if no local PDF yet and paper has a DOI
        if paper and (not paper.pdf_path or paper.pdf_path.startswith("url:")) and paper.doi:
            oa_url = await _run_in_executor(unpaywall_src.get_oa_pdf_url, paper.doi)
            if oa_url:
                local_path = await _run_in_executor(
                    unpaywall_src.download_pdf, oa_url, paper_id, _DATA_DIR
                )
                if local_path:
                    paper.pdf_path = local_path

        if (
            paper
            and paper.pdf_path
            and not paper.pdf_path.startswith("url:")
            and Path(paper.pdf_path).exists()
        ):
            text = await _run_in_executor(extract_text, paper.pdf_path)
            if text:
                paper.full_text = text
                text_path = Path(_DATA_DIR) / "text" / f"{id_safe(paper_id)}.txt"
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(text, encoding="utf-8")
                paper.text_path = str(text_path)

    if paper:
        paper.fetched_at = _now()
        if not lib.add(paper):
            lib.update(paper)
        result = paper.to_dict()
        if not result.get("full_text"):
            if paper.doi:
                doi_filename = paper.doi.replace("/", "_")
                result["_ingest_hint"] = (
                    f"No open-access PDF found. To ingest manually:\n"
                    f"1. Download the PDF from your institution\n"
                    f"2. Save it as: {doi_filename}.pdf\n"
                    f"3. Drop it in: ~/ClaudeProjects/QuantResearcher/library/inbox/\n"
                    f"4. Run: ~/ClaudeProjects/QuantResearcher/library/ingest.sh\n"
                    f"   or in Claude Code: ingest_folder()"
                )
            else:
                result["_ingest_hint"] = (
                    f"No open-access PDF found. If you have institutional access, download the PDF "
                    f"and run: ingest_pdf(file_path='/path/to/paper.pdf', paper_id='{paper_id}')"
                )
        return result

    return {"error": f"Could not fetch paper: {paper_id}"}


@mcp.tool()
async def read_paper(paper_id: str) -> str:
    """
    Return the full text of a stored paper (capped at 50,000 characters).
    Use this to put a paper's content into context for analysis or implementation.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    lib = _get_library()
    paper = lib.get(paper_id)

    if paper is None:
        return f"Paper not found in library: {paper_id}. Use fetch_paper first."

    # Try in-memory full_text first
    if paper.full_text:
        return paper.full_text[:50_000]

    # Try reading from text file
    if paper.text_path and Path(paper.text_path).exists():
        try:
            text = Path(paper.text_path).read_text(encoding="utf-8")
            return text[:50_000]
        except Exception:
            pass

    # Fall back to abstract
    if paper.abstract:
        return f"[Full text not available. Abstract only]\n\n{paper.abstract}"

    return f"No text available for {paper_id}. Use fetch_paper to download it."


@mcp.tool()
async def find_similar(paper_id: str, n: int = 10) -> list[dict]:
    """
    Find papers similar to the given one, combining vector similarity and
    Semantic Scholar recommendations where available.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        n: Number of similar papers to return
    """
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()

    async def _vector_similar():
        return await _run_in_executor(lib.search_similar, paper_id, n)

    async def _s2_recommendations():
        return await _run_in_executor(semantic_src.get_recommendations, paper_id, n, _DATA_DIR)

    vector_papers, s2_papers = await asyncio.gather(_vector_similar(), _s2_recommendations())

    # Combine, dedup by ID, vector results take priority
    seen: set[str] = set()
    combined: list[Paper] = []

    for paper in vector_papers:
        if paper.id not in seen:
            seen.add(paper.id)
            combined.append(paper)

    for paper in s2_papers:
        if paper.id not in seen and paper.id != paper_id:
            seen.add(paper.id)
            combined.append(paper)

    # Save new S2 recommendations to library
    for paper in s2_papers:
        paper.fetched_at = _now()
        lib.add(paper)

    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(combined[:n])]


@mcp.tool()
async def search_library(query: str, n: int = 10) -> list[dict]:
    """
    Semantic search across locally stored papers only. No network calls.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        query: Search query string
        n: Number of results to return
    """
    lib = _get_library()
    papers = await _run_in_executor(lib.search_semantic, query, n)
    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(papers)]


@mcp.tool()
async def list_library(source: str | None = None) -> list[dict]:
    """
    List all papers in the local library, optionally filtered by source.

    Args:
        source: Optional filter: "arxiv", "semantic_scholar", "pubmed", "ssrn"
    """
    lib = _get_library()
    papers = lib.list_all()

    if source:
        papers = [p for p in papers if p.source == source]

    papers.sort(key=lambda p: p.fetched_at or "", reverse=True)
    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(papers)]


@mcp.tool()
async def get_citations(paper_id: str) -> list[dict]:
    """
    Get papers that cite the given paper, via Semantic Scholar.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()
    papers = await _run_in_executor(semantic_src.get_citations, paper_id, 50, _DATA_DIR)

    for paper in papers:
        paper.fetched_at = _now()
        lib.add(paper)

    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(papers)]


@mcp.tool()
async def fetch_ssrn(url: str) -> dict:
    """
    Fetch an SSRN paper by URL. Stores metadata and abstract.
    PDF download is attempted but failure is silent.

    Args:
        url: SSRN paper URL, e.g. https://papers.ssrn.com/abstract=1234567
    """
    from qws_researcher.sources import ssrn as ssrn_src  # noqa: PLC0415

    lib = _get_library()
    paper = await _run_in_executor(ssrn_src.fetch_by_url, url, _DATA_DIR)
    paper.fetched_at = _now()

    if not lib.add(paper):
        lib.update(paper)

    return paper.to_dict()


@mcp.tool()
async def ingest_pdf(
    file_path: str,
    paper_id: str | None = None,
    title: str | None = None,
    authors: list[str] | None = None,
) -> dict:
    """
    Ingest a locally downloaded PDF into the paper library.
    Use this when fetch_paper returns no full text due to a paywall.

    Args:
        file_path: Absolute path to the PDF on your local machine
        paper_id: Paper ID to associate with (e.g. "s2:05eb..."). If omitted, generates "local:{filename}"
        title: Paper title (used if paper not already in library)
        authors: Author list (used if paper not already in library)
    """
    import shutil  # noqa: PLC0415

    from qws_researcher.extract import extract_text  # noqa: PLC0415

    pdf_file = Path(file_path)
    if not pdf_file.exists():
        return {"error": f"File not found: {file_path}"}
    if pdf_file.suffix.lower() != ".pdf":
        return {"error": f"Not a PDF file: {file_path}"}

    lib = _get_library()
    resolved_id = paper_id or f"local:{pdf_file.stem}"

    # Get existing record if present, otherwise create new Paper
    paper = lib.get(resolved_id)
    if paper is None:
        paper = Paper(
            id=resolved_id,
            title=title or pdf_file.stem,
            authors=authors or [],
            abstract="",
            source="local",
            url=str(pdf_file),
        )

    # Copy PDF to data/papers/
    dest_pdf = Path(_DATA_DIR) / "papers" / f"{id_safe(resolved_id)}.pdf"
    dest_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(pdf_file), str(dest_pdf))
    paper.pdf_path = str(dest_pdf)

    # Extract text
    text = await _run_in_executor(extract_text, str(dest_pdf))
    if not text:
        return {"error": f"Could not extract text from PDF: {file_path}"}

    paper.full_text = text
    text_path = Path(_DATA_DIR) / "text" / f"{id_safe(resolved_id)}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    paper.text_path = str(text_path)
    paper.fetched_at = _now()

    if not lib.add(paper):
        lib.update(paper)

    return paper.to_dict()


@mcp.tool()
async def library_stats() -> dict:
    """Return statistics about the local paper library."""
    lib = _get_library()
    return lib.stats()


@mcp.tool()
async def get_paper_metadata(paper_id: str) -> dict:
    """
    Return complete metadata for a paper without loading full text into context.
    Includes title, authors, abstract, DOI, citations, tags, notes, text_extractor,
    has_full_text flag, and doi_filename for campus download.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return {"error": f"Paper not found: {paper_id}"}

    doi_filename = None
    if paper.doi:
        doi_filename = paper.doi.replace("/", "_") + ".pdf"

    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "source": paper.source,
        "url": paper.url,
        "doi": paper.doi,
        "published_date": paper.published_date,
        "citations": paper.citations,
        "categories": paper.categories,
        "tags": paper.tags,
        "notes": paper.notes,
        "github_repos": paper.github_repos,
        "text_extractor": paper.text_extractor,
        "text_source": paper.text_source,
        "ingestion_status": paper.ingestion_status,
        "has_full_text": bool(
            paper.full_text or (paper.text_path and Path(paper.text_path).exists())
        ),
        "pdf_path": paper.pdf_path,
        "fetched_at": paper.fetched_at,
        "campus_download_needed": not bool(
            paper.full_text or (paper.text_path and Path(paper.text_path).exists())
        ),
        "doi_filename": doi_filename,
        "brief": paper.brief,
        "regime_tags": paper.regime_tags,
    }


@mcp.tool()
async def search_by_tag(tags: list[str]) -> list[dict]:
    """
    Filter the local library by tags. Returns papers that have ALL specified tags.
    Exact categorical filtering — complements search_library which is semantic.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        tags: Tags to filter by, e.g. ["to-implement", "volatility"]
    """
    lib = _get_library()
    papers = lib.list_all()
    tag_set = set(tags)
    matching = [p for p in papers if tag_set.issubset(set(p.tags))]
    matching.sort(key=lambda p: p.fetched_at or "", reverse=True)
    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(matching)]


@mcp.tool()
async def export_campus_list() -> str:
    """
    Generate a markdown checklist of papers that need downloading on campus.
    Saved to research/notes/campus-trip-YYYY-MM-DD.md.
    Papers are split into: DOI known (use filename convention) vs no DOI (manual search).
    Returns the file path of the generated list.
    """
    from datetime import date  # noqa: PLC0415

    lib = _get_library()
    papers = lib.list_all()

    # Papers with no full text — need campus download
    needed = [
        p for p in papers if not p.full_text and not (p.text_path and Path(p.text_path).exists())
    ]

    if not needed:
        return "No papers need downloading. All library records have full text."

    has_doi = [p for p in needed if p.doi]
    no_doi = [p for p in needed if not p.doi]

    today = date.today().isoformat()
    lines = [
        f"# Campus Download List — {today}",
        "",
        "Drop downloaded PDFs in `~/ClaudeProjects/QuantResearcher/library/inbox/`",
        "then run `~/ClaudeProjects/QuantResearcher/library/ingest.sh`.",
        "",
        f"**{len(needed)} papers needed** ({len(has_doi)} with DOI, {len(no_doi)} need manual search)",
        "",
    ]

    if has_doi:
        lines += [
            "## Ready to Download — Use DOI Filename",
            "",
            "Save each PDF as the filename shown, drop in inbox/, run ingest.sh.",
            "",
        ]
        for p in sorted(has_doi, key=lambda x: x.title):
            doi_filename = p.doi.replace("/", "_") + ".pdf"
            year = p.published_date[:4] if p.published_date else "?"
            authors_str = ", ".join(p.authors[:2]) + (" et al." if len(p.authors) > 2 else "")
            tags_str = f" `{'` `'.join(p.tags)}`" if p.tags else ""
            lines += [
                f"- [ ] **{p.title}** ({year})\n",
                f"      {authors_str}\n",
                f"      ID: `{p.id}`\n",
                f"      DOI: `{p.doi}`\n",
                f"      Filename: `{doi_filename}`\n",
                f"      Tags: `{tags_str}`",
                "",
            ]

    if no_doi:
        lines += [
            "## Needs Manual Search (no DOI in library)",
            "",
            "Search by title, download, then run `ingest_pdf(file_path=..., paper_id=...)`.",
            "",
        ]
        for p in sorted(no_doi, key=lambda x: x.title):
            year = p.published_date[:4] if p.published_date else "?"
            authors_str = ", ".join(p.authors[:2]) + (" et al." if len(p.authors) > 2 else "")
            tags_str = f" `{'` `'.join(p.tags)}`" if p.tags else ""
            lines += [
                f"- [ ] **{p.title}** ({year})\n",
                f"      {authors_str}\n",
                f"      ID: `{p.id}`\n",
                f"      URL: {p.url}{tags_str}\n",
                "",
            ]

    content = "\n".join(lines)

    notes_dir = Path.home() / "ClaudeProjects/QuantResearcher/research/notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    out_path = notes_dir / f"campus-trip-{today}.md"
    out_path.write_text(content, encoding="utf-8")

    return str(out_path)


@mcp.tool()
async def read_abstract(paper_id: str) -> str:
    """
    Return the abstract of a paper without loading full text.
    Faster than read_paper when deciding whether to bookmark.
    If not in library, fetches metadata only from the source (no PDF download).

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    from qws_researcher.sources import arxiv as arxiv_src  # noqa: PLC0415
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()
    paper = lib.get(paper_id)

    if paper is None:
        # Fetch metadata only — no PDF
        if paper_id.startswith("arxiv:"):
            arxiv_id = paper_id.removeprefix("arxiv:")
            papers = await _run_in_executor(arxiv_src.search, f"id:{arxiv_id}", None, 1, _DATA_DIR)
            paper = papers[0] if papers else None
        elif paper_id.startswith("s2:"):
            s2_id = paper_id.removeprefix("s2:")
            papers = await _run_in_executor(semantic_src.search, f"id:{s2_id}", None, 1, _DATA_DIR)
            paper = papers[0] if papers else None

    if paper is None or not paper.abstract:
        return f"No abstract available for {paper_id}"

    year = paper.published_date[:4] if paper.published_date else None
    authors_str = ", ".join(paper.authors[:3])
    if len(paper.authors) > 3:
        authors_str += " et al."
    header = f"**{paper.title}**"
    if authors_str or year:
        header += f"\n{authors_str}{' (' + year + ')' if year else ''}"

    if paper.brief:
        return f"{header}\n\n{paper.brief}"
    return f"{header}\n\n{paper.abstract}"


@mcp.tool()
async def get_brief(paper_id: str) -> str:
    """
    Return the pre-computed 3-sentence intelligence brief for a paper.
    Covers: what was tested, what was found, the key caveat.
    Falls back to raw abstract if brief not yet generated.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if not paper:
        return f"Paper {paper_id} not found"
    if paper.brief:
        return paper.brief
    if paper.abstract:
        return f"[Brief not yet generated]\n\n{paper.abstract}"
    return f"No content available for {paper_id}"


@mcp.tool()
async def get_regime_tags(paper_id: str) -> dict:
    """
    Return the regime tags for a paper (asset class, frequency, time period, etc.).
    Returns empty dict if tags not yet generated.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if not paper:
        return {"error": f"Paper {paper_id} not found"}
    return paper.regime_tags or {}


@mcp.tool()
async def find_papers_by_regime(
    asset_class: str | None = None,
    frequency: str | None = None,
    time_period: str | None = None,
    market_cap: str | None = None,
    market_condition: str | None = None,
) -> list[dict]:
    """
    Find papers by market regime tags. All parameters are optional — combine any.

    IMPORTANT: Display results as a table with columns: Title, Asset Class, Frequency, Time Period, ID

    asset_class options: US_equity, international_equity, futures, crypto, fixed_income, FX, commodities, multi_asset
    frequency options: tick, intraday, daily, weekly, monthly
    time_period options: pre_1990, 1990s, 2000s, 2010s, 2020s, multi_decade
    market_cap options: large_cap, small_cap, all_cap
    market_condition options: high_vol, low_vol, trending, mean_reverting, crisis

    Args:
        asset_class: Filter by asset class
        frequency: Filter by data frequency
        time_period: Filter by sample time period
        market_cap: Filter by market cap focus
        market_condition: Filter by market condition
    """
    lib = _get_library()
    papers = lib.find_by_regime(
        asset_class=asset_class,
        frequency=frequency,
        time_period=time_period,
        market_cap=market_cap,
        market_condition=market_condition,
    )
    return [
        {
            "id": p.id,
            "title": (p.title or "")[:60],
            "regime_tags": p.regime_tags or {},
            "ingestion_status": p.ingestion_status,
            "has_brief": bool(p.brief),
        }
        for p in papers
    ]


@mcp.tool()
async def bookmark_paper(
    paper_id: str,
    reason: str | None = None,
    tags: list[str] = [],
) -> dict:
    """
    Save a paper to your library and add it to the campus trip list if no full text.
    Use this after search_papers to commit to a paper.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        reason: Why you're bookmarking (stored as note and in campus list)
        tags: Tags to add, e.g. ["to-read", "volatility"]
    """
    from qws_researcher.sources import arxiv as arxiv_src  # noqa: PLC0415
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()
    paper = lib.get(paper_id)

    if paper is None:
        # Fetch metadata to populate the library record
        if paper_id.startswith("arxiv:"):
            arxiv_id = paper_id.removeprefix("arxiv:")
            papers = await _run_in_executor(arxiv_src.search, f"id:{arxiv_id}", None, 1, _DATA_DIR)
            paper = papers[0] if papers else None
        elif paper_id.startswith("s2:"):
            papers = await _run_in_executor(semantic_src.search, paper_id, None, 1, _DATA_DIR)
            paper = next((p for p in papers if p.id == paper_id), None)

        if paper is None:
            return {"status": "error", "message": f"Could not find paper: {paper_id}"}

        paper.fetched_at = _now()
        lib.add(paper)

    # Apply tags
    existing = set(paper.tags)
    paper.tags = paper.tags + [t for t in tags if t not in existing]

    # Append reason as note
    if reason:
        paper.notes = f"{paper.notes}\n\n{reason}" if paper.notes else reason

    lib.update(paper)

    # Crossref DOI fail-safe: if the paper has no DOI, try a fuzzy lookup by title+author.
    # Persist the recovered DOI so downstream steps (Unpaywall, campus filename) can use it.
    if not paper.doi and paper.title:
        from qws_researcher.sources import crossref as crossref_src  # noqa: PLC0415

        first_author = paper.authors[0] if paper.authors else None
        recovered_doi = await _run_in_executor(crossref_src.lookup_doi, paper.title, first_author)
        if recovered_doi:
            paper.doi = recovered_doi
            lib.update(paper)

    has_full_text = bool(paper.full_text or (paper.text_path and Path(paper.text_path).exists()))
    campus_trip_needed = not has_full_text

    filename_hint = None
    if paper.doi:
        filename_hint = paper.doi.replace("/", "_") + ".pdf"

    if campus_trip_needed:
        year_int = None
        if paper.published_date:
            try:
                year_int = int(paper.published_date[:4])
            except ValueError:
                pass

        campus = _get_campus_list()
        entry = CampusEntry(
            paper_id=paper.id,
            title=paper.title,
            authors=paper.authors,
            year=year_int,
            doi=paper.doi,
            filename_hint=filename_hint,
            source=paper.source,
            url=paper.url,
            abstract=paper.abstract or None,
            tags=paper.tags,
            added_at=_now(),
            reason=reason,
        )
        campus.add(entry)

    return {
        "status": "bookmarked",
        "title": paper.title,
        "campus_trip_needed": campus_trip_needed,
        "filename_hint": filename_hint,
        "abstract_saved": bool(paper.abstract),
        "message": (
            f"Added to campus trip list. Download as: {filename_hint}"
            if campus_trip_needed and filename_hint
            else "Added to campus trip list. No DOI — search by title on campus."
            if campus_trip_needed
            else "Full text already available."
        ),
    }


@mcp.tool()
async def list_needed(tags: list[str] | None = None) -> dict:
    """
    List papers on your campus trip list. Optionally filter by tags.

    Args:
        tags: If provided, only return papers that have ALL specified tags
    """
    campus = _get_campus_list()
    entries = campus.list_all()

    if tags:
        tag_set = set(tags)
        entries = [e for e in entries if tag_set.issubset(set(e.tags))]

    entries.sort(key=lambda e: e.added_at, reverse=True)

    return {
        "total": len(entries),
        "papers": [
            {
                "paper_id": e.paper_id,
                "title": e.title,
                "filename_hint": e.filename_hint,
                "doi": e.doi,
                "reason": e.reason,
                "tags": e.tags,
                "added": e.added_at,
                "url": e.url,
            }
            for e in entries
        ],
    }


@mcp.tool()
async def campus_list_stats() -> dict:
    """Summary of your campus trip list."""
    campus = _get_campus_list()
    entries = campus.list_all()

    all_tags: list[str] = []
    for e in entries:
        all_tags.extend(e.tags)
    unique_tags = sorted(set(all_tags))

    return {
        "total": len(entries),
        "with_doi_hint": sum(1 for e in entries if e.filename_hint),
        "without_doi_hint": sum(1 for e in entries if not e.filename_hint),
        "tags": unique_tags,
    }


@mcp.tool()
async def remove_from_campus_list(paper_id: str) -> str:
    """
    Remove a paper from the campus trip list.
    Use this to clean up test entries or papers you no longer need to download.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
    """
    campus = _get_campus_list()
    removed = campus.remove(paper_id)
    if removed:
        return f"Removed {paper_id} from campus list."
    return f"{paper_id} was not in campus list."


@mcp.tool()
async def bulk_bookmark(
    paper_ids: list[str],
    reason: str | None = None,
    tags: list[str] = [],
) -> dict:
    """
    Bookmark multiple papers at once with shared tags and an optional reason note.

    Args:
        paper_ids: List of paper IDs to bookmark
        reason: Optional note appended to each paper (e.g. "Needed for HAR implementation")
        tags: Tags to add to each paper, e.g. ["to-read", "volatility"]
    """
    lib = _get_library()
    bookmarked = 0
    already_have_full_text = 0
    not_found = 0
    details = []

    for pid in paper_ids:
        paper = lib.get(pid)
        if paper is None:
            not_found += 1
            details.append({"id": pid, "status": "not_found"})
            continue

        existing = set(paper.tags)
        new_tags = [t for t in tags if t not in existing]
        paper.tags = paper.tags + new_tags

        if reason:
            if paper.notes:
                paper.notes = f"{paper.notes}\n\n{reason}"
            else:
                paper.notes = reason

        lib.update(paper)
        has_text = bool(paper.full_text or (paper.text_path and Path(paper.text_path).exists()))
        if has_text:
            already_have_full_text += 1
        bookmarked += 1
        details.append({"id": pid, "status": "bookmarked", "has_full_text": has_text})

    return {
        "bookmarked": bookmarked,
        "already_have_full_text": already_have_full_text,
        "not_found": not_found,
        "details": details,
    }


@mcp.tool()
async def update_note(paper_id: str, note: str) -> str:
    """
    Replace the research note on a paper entirely. Use add_note to append instead.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        note: New note text (replaces existing note)
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    old_len = len(paper.notes) if paper.notes else 0
    paper.notes = note
    lib.update(paper)
    return f"Note updated for {paper_id} (old: {old_len} chars, new: {len(note)} chars)"


@mcp.tool()
async def remove_tag(paper_id: str, tags: list[str]) -> str:
    """
    Remove one or more tags from a paper. Silently ignores tags that aren't present.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        tags: Tags to remove
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    remove_set = set(tags)
    paper.tags = [t for t in paper.tags if t not in remove_set]
    lib.update(paper)
    return f"Tags updated for {paper_id}: {paper.tags}"


@mcp.tool()
async def reading_list() -> list[dict]:
    """
    Papers tagged 'to-read' sorted by citation count descending.
    Prioritizes most influential unread papers first.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID
    Never omit columns. Never reformat. Use the values exactly as returned.
    """
    lib = _get_library()
    papers = [p for p in lib.list_all() if "to-read" in p.tags]
    papers.sort(key=lambda p: p.citations or 0, reverse=True)
    return [StandardSearchResult.from_paper(p, i + 1).to_dict() for i, p in enumerate(papers)]


@mcp.tool()
async def get_related_papers(paper_id: str, n: int = 15) -> list[dict]:
    """
    Combines three signals into one ranked list:
    1. Vector similarity from local library
    2. Semantic Scholar recommendations (if s2 ID available)
    3. Papers in library that share tags with this paper
    Deduplicates by paper_id, returns top n unique results.

    IMPORTANT: Always display results as a table with ALL of these columns in this exact order:
    #, Title, Authors, Year, Citations, Source, Abstract, Full Text, ID, Signal
    Never omit columns. Never reformat. Use the values exactly as returned.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        n: Number of results to return
    """
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()

    async def _vector():
        return await _run_in_executor(lib.search_similar, paper_id, n)

    async def _s2():
        return await _run_in_executor(semantic_src.get_recommendations, paper_id, n, _DATA_DIR)

    vector_papers, s2_papers = await asyncio.gather(_vector(), _s2())

    # Signal 3: shared-tag papers (sync, cheap)
    target = lib.get(paper_id)
    target_tags = set(target.tags) if target else set()
    shared_tag_papers = []
    if target_tags:
        shared_tag_papers = [
            p for p in lib.list_all() if p.id != paper_id and target_tags.intersection(set(p.tags))
        ]
        shared_tag_papers.sort(key=lambda p: p.citations or 0, reverse=True)

    seen: set[str] = set()
    combined: list[tuple[Paper, str]] = []

    for paper in vector_papers:
        if paper.id not in seen and paper.id != paper_id:
            seen.add(paper.id)
            combined.append((paper, "vector"))

    for paper in s2_papers:
        if paper.id not in seen and paper.id != paper_id:
            seen.add(paper.id)
            combined.append((paper, "s2_recommendations"))

    for paper in shared_tag_papers:
        if paper.id not in seen:
            seen.add(paper.id)
            combined.append((paper, "shared_tags"))

    # Save new S2 recommendations to library
    for paper in s2_papers:
        paper.fetched_at = _now()
        lib.add(paper)

    results = []
    for i, (paper, signal) in enumerate(combined[:n]):
        d = StandardSearchResult.from_paper(paper, i + 1).to_dict()
        d["Signal"] = signal
        results.append(d)
    return results


@mcp.tool()
async def cite(paper_id: str, format: str = "bibtex") -> str:
    """
    Generate a citation for a paper from stored metadata. No network calls.
    Formats: 'bibtex', 'apa', 'chicago'

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        format: Citation format — 'bibtex', 'apa', or 'chicago'
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    year = paper.published_date[:4] if paper.published_date else None
    cite_key = id_safe(paper_id)

    if format == "bibtex":

        def _bibtex_author(name: str) -> str:
            parts = name.strip().split()
            if len(parts) >= 2:
                return f"{parts[-1]}, {' '.join(parts[:-1])}"
            return name

        author_str = (
            " and ".join(_bibtex_author(a) for a in paper.authors) if paper.authors else "Unknown"
        )
        missing = []
        if not paper.authors:
            missing.append("authors")
        if not year:
            missing.append("year")

        lines = [f"@article{{{cite_key},"]
        lines.append(f"  title   = {{{paper.title}}},")
        lines.append(f"  author  = {{{author_str}}},")
        lines.append(f"  year    = {{{year or '????'}}},")
        if paper.doi:
            lines.append(f"  doi     = {{{paper.doi}}},")
        lines.append(f"  url     = {{{paper.url}}}")
        lines.append("}")
        if missing:
            lines.append(f"% NOTE: missing fields: {', '.join(missing)}")
        return "\n".join(lines)

    def _short_author(name: str) -> str:
        parts = name.strip().split()
        if len(parts) >= 2:
            initials = ". ".join(p[0] for p in parts[:-1]) + "."
            return f"{parts[-1]}, {initials}"
        return name

    if format == "apa":
        if paper.authors:
            authors_str = ", ".join(_short_author(a) for a in paper.authors[:6])
            if len(paper.authors) > 6:
                authors_str += ", ... " + _short_author(paper.authors[-1])
        else:
            authors_str = "Unknown"
        year_str = f"({year})" if year else "(n.d.)"
        return f"{authors_str} {year_str}. {paper.title}. {paper.url}"

    if format == "chicago":
        if paper.authors:
            first = paper.authors[0]
            parts = first.strip().split()
            first_fmt = f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else first
            rest = [_short_author(a) for a in paper.authors[1:]]
            authors_str = ", ".join([first_fmt] + rest) if rest else first_fmt
        else:
            authors_str = "Unknown"
        year_str = year or "n.d."
        return f'{authors_str}. "{paper.title}." {year_str}. {paper.url}'

    return f"Unrecognized format '{format}'. Use: bibtex, apa, chicago"


@mcp.tool()
async def ingest_folder() -> dict:
    """
    Process all PDFs in ~/ClaudeProjects/QuantResearcher/library/inbox/.
    PDFs named by DOI (e.g. 10.1016_j.najef.2026.102605.pdf) that match a library
    record are ingested; others move to unmatched/ for manual handling.
    """
    from qws_researcher.ingest import ingest_folder as _ingest_folder  # noqa: PLC0415

    inbox = str(Path.home() / "ClaudeProjects/QuantResearcher/library/inbox")
    ingested_dir = str(Path.home() / "ClaudeProjects/QuantResearcher/library/ingested")
    unmatched_dir = str(Path.home() / "ClaudeProjects/QuantResearcher/library/unmatched")
    result = await _run_in_executor(_ingest_folder, inbox, ingested_dir, unmatched_dir, _DATA_DIR)

    # Clear successfully ingested papers from campus trip list
    ingested_ids = [item["paper_id"] for item in result.get("ingested", [])]
    if ingested_ids:
        campus = _get_campus_list()
        cleared = campus.clear_ingested(ingested_ids)
        result["campus_list_cleared"] = cleared

    return result


@mcp.tool()
async def add_note(paper_id: str, note: str) -> str:
    """
    Append a research note to a paper in the local library.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        note: Note text to append
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    if paper.notes:
        paper.notes = f"{paper.notes}\n\n{note}"
    else:
        paper.notes = note

    lib.update(paper)
    return f"Note added to {paper_id}"


@mcp.tool()
async def tag_paper(paper_id: str, tags: list[str]) -> str:
    """
    Add tags to a paper in the local library. Existing tags are preserved.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        tags: Tags to add, e.g. ["volatility", "implemented", "to-read"]
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    existing = set(paper.tags)
    new_tags = [t for t in tags if t not in existing]
    paper.tags = paper.tags + new_tags
    lib.update(paper)
    return f"Tags updated for {paper_id}: {paper.tags}"


@mcp.tool()
async def add_repo(paper_id: str, repo: str, notes: str | None = None) -> str:
    """
    Link a GitHub repository to a paper in your library.
    Use this after finding a reference implementation on GitHub.

    Args:
        paper_id: Paper ID like "arxiv:2301.00001"
        repo: Repository in "owner/repo" format, e.g. "turboPutty/rBergomi"
        notes: Optional note about this repo, e.g. "official implementation"
    """
    lib = _get_library()
    paper = lib.get(paper_id)
    if paper is None:
        return f"Paper not found: {paper_id}"

    if repo not in paper.github_repos:
        paper.github_repos = paper.github_repos + [repo]
        lib.update(paper)

    note_suffix = f" — {notes}" if notes else ""
    return f"Linked {repo}{note_suffix} to {paper_id}. Repos: {paper.github_repos}"


@mcp.tool()
async def fix_metadata(dry_run: bool = True) -> dict:
    """
    Scan library for papers with bad metadata (title missing or set to a URL).
    dry_run=True (default): return affected papers without changing anything.
    dry_run=False: re-fetch metadata from source and update library records.
    Preserves full_text, notes, tags, and all user data.

    Args:
        dry_run: If False, actually fix the records. Defaults to True for safety.
    """
    from qws_researcher.sources import arxiv as arxiv_src  # noqa: PLC0415
    from qws_researcher.sources import semantic as semantic_src  # noqa: PLC0415

    lib = _get_library()
    all_papers = lib.list_all()

    bad = [p for p in all_papers if not p.title or p.title.startswith("http")]

    if not bad:
        return {"affected": 0, "papers": [], "message": "No bad metadata found."}

    if dry_run:
        return {
            "affected": len(bad),
            "dry_run": True,
            "papers": [{"id": p.id, "title": p.title, "url": p.url} for p in bad],
            "message": "Run fix_metadata(dry_run=False) to repair these records.",
        }

    fixed = 0
    failed = 0
    details = []

    for paper in bad:
        try:
            fresh = None
            if paper.id.startswith("arxiv:"):
                arxiv_id = paper.id.removeprefix("arxiv:")
                results = await _run_in_executor(
                    arxiv_src.search, f"id:{arxiv_id}", None, 1, _DATA_DIR
                )
                fresh = results[0] if results else None
            elif paper.id.startswith("s2:"):
                s2_id = paper.id.removeprefix("s2:")
                results = await _run_in_executor(semantic_src.search, s2_id, None, 1, _DATA_DIR)
                fresh = next((p for p in results if p.id == paper.id), None)

            if fresh and fresh.title and not fresh.title.startswith("http"):
                # Update only metadata fields — preserve user data
                paper.title = fresh.title
                if fresh.abstract:
                    paper.abstract = fresh.abstract
                if fresh.authors:
                    paper.authors = fresh.authors
                if fresh.published_date:
                    paper.published_date = fresh.published_date
                if fresh.citations is not None:
                    paper.citations = fresh.citations
                if fresh.doi and not paper.doi:
                    paper.doi = fresh.doi
                lib.update(paper)
                fixed += 1
                details.append({"id": paper.id, "status": "fixed", "new_title": paper.title})
            else:
                failed += 1
                details.append({"id": paper.id, "status": "could_not_fetch", "url": paper.url})

        except Exception as e:
            failed += 1
            details.append({"id": paper.id, "status": "error", "error": str(e)})

    return {
        "affected": len(bad),
        "fixed": fixed,
        "failed": failed,
        "dry_run": False,
        "details": details,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
