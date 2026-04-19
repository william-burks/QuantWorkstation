from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_FILENAME = "campus_list.json"


@dataclass
class CampusEntry:
    paper_id: str
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    filename_hint: str | None  # doi.replace("/","_",1)+".pdf" if DOI known
    source: str
    url: str
    abstract: str | None
    tags: list[str]
    added_at: str
    reason: str | None


class CampusList:
    def __init__(self, data_dir: str = "data") -> None:
        self._path = Path(data_dir) / _FILENAME
        self._entries: dict[str, CampusEntry] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = {k: CampusEntry(**v) for k, v in raw.items()}
            except Exception as e:
                logger.warning("Failed to load campus list: %s", e)
                self._entries = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({k: asdict(v) for k, v in self._entries.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save campus list: %s", e)

    def add(self, entry: CampusEntry) -> bool:
        """Add entry. Returns False if paper_id already present."""
        if entry.paper_id in self._entries:
            return False
        self._entries[entry.paper_id] = entry
        self._save()
        return True

    def remove(self, paper_id: str) -> bool:
        """Remove by paper_id. Returns False if not found."""
        if paper_id not in self._entries:
            return False
        del self._entries[paper_id]
        self._save()
        return True

    def list_all(self) -> list[CampusEntry]:
        return list(self._entries.values())

    def clear_ingested(self, paper_ids: list[str]) -> int:
        """Remove all entries whose paper_id is in the list. Returns count removed."""
        removed = 0
        for pid in paper_ids:
            if pid in self._entries:
                del self._entries[pid]
                removed += 1
        if removed:
            self._save()
        return removed
