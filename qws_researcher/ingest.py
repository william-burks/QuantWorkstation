from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from qws_researcher import id_safe
from qws_researcher.extract import extract_text
from qws_researcher.store.library import PaperLibrary

logger = logging.getLogger(__name__)

# Matches DOI-as-filename: 10.XXXX_rest.pdf
# The first _ after 10.\d+ is the / separator; all subsequent _ are literal
_DOI_FILENAME_RE = re.compile(r"^(10\.\d{4,})_(.+)\.pdf$", re.IGNORECASE)


def _parse_doi(filename: str) -> str | None:
    """
    Convert DOI filename back to DOI string.
    e.g. "10.1016_j.najef.2026.102605.pdf" -> "10.1016/j.najef.2026.102605"
    Returns None if filename doesn't match the convention.
    """
    m = _DOI_FILENAME_RE.match(filename)
    if not m:
        return None
    prefix, rest = m.group(1), m.group(2)
    return f"{prefix}/{rest}"


def ingest_folder(
    inbox: str,
    ingested_dir: str,
    unmatched_dir: str,
    data_dir: str,
) -> dict[str, list[dict[str, Any]]]:
    """
    Process all PDFs in inbox/:
    - DOI filename + DOI in library → extract text, update record, move to ingested/
    - DOI filename but DOI not in library → move to unmatched/
    - Non-DOI filename → move to unmatched/

    Returns {"ingested": [...], "unmatched": [...], "errors": [...]}
    """
    inbox_path = Path(inbox)
    ingested_path = Path(ingested_dir)
    unmatched_path = Path(unmatched_dir)

    for d in (ingested_path, unmatched_path):
        d.mkdir(parents=True, exist_ok=True)

    lib = PaperLibrary(data_dir=data_dir)
    result: dict[str, list[dict[str, Any]]] = {"ingested": [], "unmatched": [], "errors": []}

    pdf_files = sorted(inbox_path.glob("*.pdf"))
    if not pdf_files:
        return result

    for pdf_file in pdf_files:
        try:
            doi = _parse_doi(pdf_file.name)

            if doi is None:
                logger.info("Non-DOI filename, moving to unmatched: %s", pdf_file.name)
                shutil.move(str(pdf_file), str(unmatched_path / pdf_file.name))
                result["unmatched"].append({"file": pdf_file.name, "reason": "non-DOI filename"})
                continue

            paper = lib.find_by_doi(doi)

            if paper is None:
                logger.info("DOI not in library (%s), moving to unmatched: %s", doi, pdf_file.name)
                shutil.move(str(pdf_file), str(unmatched_path / pdf_file.name))
                result["unmatched"].append(
                    {"file": pdf_file.name, "reason": f"DOI not in library: {doi}"}
                )
                continue

            # Copy PDF to data/papers/
            papers_dir = Path(data_dir) / "papers"
            papers_dir.mkdir(parents=True, exist_ok=True)
            dest_pdf = papers_dir / f"{id_safe(paper.id)}.pdf"
            shutil.copy2(str(pdf_file), str(dest_pdf))
            paper.pdf_path = str(dest_pdf)

            # Extract text
            text = extract_text(str(dest_pdf))
            if not text:
                result["errors"].append({"file": pdf_file.name, "error": "text extraction failed"})
                continue

            paper.full_text = text
            paper.text_extractor = "pymupdf4llm"

            text_path = Path(data_dir) / "text" / f"{id_safe(paper.id)}.txt"
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            paper.text_path = str(text_path)

            lib.update(paper)

            # Move original PDF to ingested/
            shutil.move(str(pdf_file), str(ingested_path / pdf_file.name))
            result["ingested"].append(
                {"file": pdf_file.name, "paper_id": paper.id, "title": paper.title}
            )
            logger.info("Ingested: %s -> %s", pdf_file.name, paper.id)

        except Exception as e:
            logger.error("Error processing %s: %s", pdf_file.name, e)
            result["errors"].append({"file": pdf_file.name, "error": str(e)})

    return result
