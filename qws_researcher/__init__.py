from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Paper:
    id: str  # "arxiv:2301.00001", "pmid:12345", "ssrn:4567890"
    title: str | None
    authors: list[str]
    abstract: str
    source: str  # "arxiv" | "semantic_scholar" | "pubmed" | "ssrn"
    url: str
    full_text: str | None = None
    pdf_path: str | None = None
    text_path: str | None = None
    published_date: str | None = None
    categories: list[str] = field(default_factory=list)
    citations: int | None = None
    references: list[str] = field(default_factory=list)
    fetched_at: str = ""
    doi: str | None = None
    text_extractor: str | None = (
        None  # "pymupdf4llm", "nougat", "nougat-low-confidence", or None (legacy)
    )
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    github_repos: list[str] = field(default_factory=list)
    brief: str | None = None
    regime_tags: dict[str, Any] | None = None  # {"asset_class": "futures", "frequency": "daily", ...}
    method_summary: dict[str, Any] | None = None
    results_snapshot: list[Any] | None = None
    assumptions: list[str] | None = None
    constructs: list[str] | None = None
    ingestion_status: str = "abstract_only"
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "source": self.source,
            "url": self.url,
            "full_text": self.full_text,
            "pdf_path": self.pdf_path,
            "text_path": self.text_path,
            "published_date": self.published_date,
            "categories": self.categories,
            "citations": self.citations,
            "references": self.references,
            "fetched_at": self.fetched_at,
            "doi": self.doi,
            "text_extractor": self.text_extractor,
            "notes": self.notes,
            "tags": self.tags,
            "github_repos": self.github_repos,
            "brief": self.brief,
            "regime_tags": self.regime_tags,
            "method_summary": self.method_summary,
            "results_snapshot": self.results_snapshot,
            "assumptions": self.assumptions,
            "constructs": self.constructs,
            "ingestion_status": self.ingestion_status,
            "error_detail": self.error_detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paper:
        return cls(
            id=data["id"],
            title=data["title"],
            authors=data.get("authors", []),
            abstract=data.get("abstract", ""),
            source=data.get("source", ""),
            url=data.get("url", ""),
            full_text=data.get("full_text"),
            pdf_path=data.get("pdf_path"),
            text_path=data.get("text_path"),
            published_date=data.get("published_date"),
            categories=data.get("categories", []),
            citations=data.get("citations"),
            references=data.get("references", []),
            fetched_at=data.get("fetched_at", ""),
            doi=data.get("doi"),
            text_extractor=data.get("text_extractor"),
            notes=data.get("notes"),
            tags=data.get("tags", []),
            github_repos=data.get("github_repos", []),
            brief=data.get("brief"),
            regime_tags=data.get("regime_tags"),
            method_summary=data.get("method_summary"),
            results_snapshot=data.get("results_snapshot"),
            assumptions=data.get("assumptions"),
            constructs=data.get("constructs"),
            ingestion_status=data.get("ingestion_status", "abstract_only"),
            error_detail=data.get("error_detail"),
        )


@dataclass
class PaperSummary:
    id: str
    title: str
    authors: list[str]
    abstract: str
    source: str
    published_date: str | None
    citations: int | None
    url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "source": self.source,
            "published_date": self.published_date,
            "citations": self.citations,
            "url": self.url,
        }

    @classmethod
    def from_paper(cls, paper: Paper) -> PaperSummary:
        title = (
            paper.title
            if paper.title and not paper.title.startswith("http")
            else f"[No title — re-fetch {paper.id}]"
        )
        return cls(
            id=paper.id,
            title=title,
            authors=paper.authors,
            abstract=paper.abstract,
            source=paper.source,
            published_date=paper.published_date,
            citations=paper.citations,
            url=paper.url,
        )


def _format_authors(authors: list[str]) -> str:
    """Format author list as 'Last, F.' initials, max 3 then et al."""
    if not authors:
        return "[Unknown]"
    formatted = []
    for name in authors[:3]:
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            formatted.append(f"{parts[1]}, {parts[0][0]}.")
        else:
            formatted.append(name)
    result = "; ".join(formatted)
    if len(authors) > 3:
        result += "; et al."
    return result


@dataclass
class StandardSearchResult:
    row: int
    title: str
    authors: str
    year: str
    citations: str
    source: str
    has_abstract: str
    has_full_text: str
    id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "#": self.row,
            "Title": self.title,
            "Authors": self.authors,
            "Year": self.year,
            "Citations": self.citations,
            "Source": self.source,
            "Abstract": self.has_abstract,
            "Full Text": self.has_full_text,
            "ID": self.id,
        }

    @staticmethod
    def to_table(
        results: list[StandardSearchResult],
        extra_col: tuple[str, list[str]] | None = None,
    ) -> str:
        """Render results as a fixed 9-column markdown table.
        extra_col: optional (header, values) tuple to append as a 10th column."""
        headers = [
            "#",
            "Title",
            "Authors",
            "Year",
            "Citations",
            "Source",
            "Abstract",
            "Full Text",
            "ID",
        ]
        rows = [
            [
                str(r.row),
                r.title,
                r.authors,
                r.year,
                r.citations,
                r.source,
                r.has_abstract,
                r.has_full_text,
                r.id,
            ]
            for r in results
        ]
        if extra_col:
            headers = headers + [extra_col[0]]
            for i, row in enumerate(rows):
                row.append(extra_col[1][i] if i < len(extra_col[1]) else "")

        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def fmt_row(cells: list[str]) -> str:
            return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

        sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
        lines = [fmt_row(headers), sep] + [fmt_row(row) for row in rows]
        return "\n".join(lines)

    @classmethod
    def from_paper(cls, paper: Paper, row: int) -> StandardSearchResult:
        raw_title = paper.title if paper.title and not paper.title.startswith("http") else None
        if raw_title and len(raw_title) > 60:
            display_title = raw_title[:60] + "…"
        else:
            display_title = raw_title or f"[No title — re-fetch {paper.id}]"

        year = paper.published_date[:4] if paper.published_date else "—"
        citations = f"{paper.citations:,}" if paper.citations else "—"

        _source_map = {"semantic_scholar": "s2"}
        source = _source_map.get(paper.source, paper.source or "—")

        has_abstract = "✓" if paper.abstract else "✗"
        has_full_text = "✓" if (paper.full_text or paper.text_path) else "✗"

        return cls(
            row=row,
            title=display_title,
            authors=_format_authors(paper.authors),
            year=year,
            citations=citations,
            source=source,
            has_abstract=has_abstract,
            has_full_text=has_full_text,
            id=paper.id,
        )


def id_safe(paper_id: str) -> str:
    """Convert paper ID to a filesystem-safe string."""
    return paper_id.replace(":", "_").replace("/", "_").replace(" ", "_")
