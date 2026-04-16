#!/usr/bin/env python3
"""
Batch structured extraction over all papers in the library.

Reads every paper from data/research.db, runs extract_structured,
writes markdown files to data/extracts/. Skips papers that already
have an extract. Safe to re-run.

Usage:
    python -m qws_researcher.batch_extract
    python -m qws_researcher.batch_extract --data-dir qws_researcher/data
    python -m qws_researcher.batch_extract --limit 20   # process first N only
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch extract structured fields from papers")
    parser.add_argument("--data-dir", default="qws_researcher/data", help="Path to data directory")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0 = all)")
    args = parser.parse_args()

    data_dir = args.data_dir

    from qws_researcher import id_safe
    from qws_researcher.extract_structured import extract_paper
    from qws_researcher.store.library import PaperLibrary

    lib = PaperLibrary(data_dir=data_dir)
    papers = lib.list_all()

    extracts_dir = Path(data_dir) / "extracts"
    extracts_dir.mkdir(parents=True, exist_ok=True)

    if args.limit:
        papers = papers[: args.limit]

    total = len(papers)
    skipped = done = failed = 0

    logger.info("Papers in library: %d", total)

    for i, paper in enumerate(papers, 1):
        extract_path = extracts_dir / f"{id_safe(paper.id)}.md"
        if extract_path.exists():
            skipped += 1
            continue

        logger.info("[%d/%d] Extracting %s", i, total, paper.id)
        result = extract_paper(paper, data_dir=data_dir)
        if result:
            done += 1
        else:
            failed += 1

    print(f"\n{'='*50}")
    print(f"Total:    {total}")
    print(f"Done:     {done}")
    print(f"Skipped:  {skipped}  (already extracted)")
    print(f"Failed:   {failed}")
    print(f"{'='*50}")
    print(f"Extracts at: {extracts_dir}")


if __name__ == "__main__":
    main()
