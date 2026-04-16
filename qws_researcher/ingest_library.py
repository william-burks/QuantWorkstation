#!/usr/bin/env python3
"""
Terminal entry point for batch PDF ingestion from the library inbox.
Drop PDFs named by DOI (e.g. 10.1016_j.jfineco.2023.01.001.pdf) into
qws_researcher/data/inbox/, then run this script.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parent
_DATA_DIR = _ROOT / "data"
_INBOX = _DATA_DIR / "inbox"
_INGESTED = _DATA_DIR / "ingested"
_UNMATCHED = _DATA_DIR / "unmatched"

from qws_researcher.ingest import ingest_folder  # noqa: E402


def main() -> None:
    _INBOX.mkdir(parents=True, exist_ok=True)
    print(f"Processing inbox: {_INBOX}")

    result = ingest_folder(
        inbox=str(_INBOX),
        ingested_dir=str(_INGESTED),
        unmatched_dir=str(_UNMATCHED),
        data_dir=str(_DATA_DIR),
    )

    ingested = result["ingested"]
    unmatched = result["unmatched"]
    errors = result["errors"]

    print(f"\n{'='*50}")
    print(f"Ingested:   {len(ingested)}")
    print(f"Unmatched:  {len(unmatched)}")
    print(f"Errors:     {len(errors)}")
    print(f"{'='*50}")

    if ingested:
        print("\nIngested:")
        for item in ingested:
            print(f"  [OK] {item['file']}")
            print(f"       -> {item['paper_id']}: {item['title'][:60]}")

    if unmatched:
        print("\nUnmatched (moved to data/unmatched/ — rename by DOI and retry):")
        for item in unmatched:
            print(f"  [??] {item['file']}")
            print(f"       {item['reason']}")

    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"  [!!] {item['file']}: {item['error']}")


if __name__ == "__main__":
    main()
