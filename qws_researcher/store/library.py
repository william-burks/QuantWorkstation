from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from qws_researcher import Paper, PaperSummary
from qws_researcher.store.vector import VectorIndex

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    doi TEXT,
    source TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_source ON papers(source);

CREATE TABLE IF NOT EXISTS equations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL,
    latex TEXT NOT NULL,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);
CREATE INDEX IF NOT EXISTS idx_eq_paper ON equations(paper_id);
"""


class PaperLibrary:
    def __init__(self, data_dir: str = "data") -> None:
        self._data_dir = data_dir
        db_path = Path(data_dir) / "research.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._vector = VectorIndex(data_dir=data_dir)

    # --- Core CRUD ---

    def add(self, paper: Paper) -> bool:
        """Add a paper. Returns False if already exists."""
        try:
            self._conn.execute(
                "INSERT INTO papers (id, doi, source, data) VALUES (?, ?, ?, ?)",
                (paper.id, paper.doi, paper.source, json.dumps(paper.to_dict())),
            )
            self._conn.commit()
            self._upsert_vector(paper)
            return True
        except sqlite3.IntegrityError:
            return False

    def update(self, paper: Paper) -> None:
        """Update an existing paper record."""
        self._conn.execute(
            "INSERT OR REPLACE INTO papers (id, doi, source, data) VALUES (?, ?, ?, ?)",
            (paper.id, paper.doi, paper.source, json.dumps(paper.to_dict())),
        )
        self._conn.commit()
        self._upsert_vector(paper)

    def get(self, paper_id: str) -> Paper | None:
        row = self._conn.execute("SELECT data FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return Paper.from_dict(json.loads(row[0])) if row else None

    def find_by_doi(self, doi: str) -> Paper | None:
        row = self._conn.execute("SELECT data FROM papers WHERE doi = ?", (doi,)).fetchone()
        return Paper.from_dict(json.loads(row[0])) if row else None

    def list_all(self) -> list[Paper]:
        rows = self._conn.execute("SELECT data FROM papers").fetchall()
        return [Paper.from_dict(json.loads(r[0])) for r in rows]

    def delete(self, paper_id: str) -> None:
        self._conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        self._conn.execute("DELETE FROM equations WHERE paper_id = ?", (paper_id,))
        self._conn.commit()
        try:
            self._vector.delete(paper_id)
        except Exception as e:
            logger.warning("Vector delete failed for %s: %s", paper_id, e)

    # --- Search ---

    def search_semantic(self, query: str, n: int = 10) -> list[Paper]:
        try:
            results = self._vector.search(query, n=n)
            papers = []
            for paper_id, _score in results:
                paper = self.get(paper_id)
                if paper:
                    papers.append(paper)
            return papers
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []

    def search_similar(self, paper_id: str, n: int = 10) -> list[Paper]:
        try:
            results = self._vector.search_similar(paper_id, n=n)
            papers = []
            for pid, _score in results:
                paper = self.get(pid)
                if paper:
                    papers.append(paper)
            return papers
        except Exception as e:
            logger.warning("Similarity search failed for %s: %s", paper_id, e)
            return []

    # --- Equations ---

    def save_equation(self, equation: dict) -> None:
        self._conn.execute(
            "INSERT INTO equations (paper_id, latex) VALUES (?, ?)",
            (equation.get("paper_id", ""), equation.get("latex", "")),
        )
        self._conn.commit()

    def get_equations(self, paper_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT paper_id, latex FROM equations WHERE paper_id = ?", (paper_id,)
        ).fetchall()
        return [{"paper_id": r[0], "latex": r[1]} for r in rows]

    def search_equations(self, latex_fragment: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT paper_id, latex FROM equations WHERE latex LIKE ?",
            (f"%{latex_fragment}%",),
        ).fetchall()
        return [{"paper_id": r[0], "latex": r[1]} for r in rows]

    # --- Regime filter ---

    def find_by_regime(
        self,
        asset_class: str | None = None,
        frequency: str | None = None,
        time_period: str | None = None,
        market_cap: str | None = None,
        market_condition: str | None = None,
    ) -> list[Paper]:
        papers = self.list_all()
        results = []
        for p in papers:
            rt = p.regime_tags or {}
            if asset_class and rt.get("asset_class") != asset_class:
                continue
            if frequency and rt.get("frequency") != frequency:
                continue
            if time_period and rt.get("time_period") != time_period:
                continue
            if market_cap and rt.get("market_cap") != market_cap:
                continue
            if market_condition and rt.get("market_condition") != market_condition:
                continue
            results.append(p)
        return results

    # --- Stats / summaries ---

    def stats(self) -> dict:
        papers = self.list_all()
        sources: dict[str, int] = {}
        dates = []
        for p in papers:
            sources[p.source] = sources.get(p.source, 0) + 1
            if p.published_date:
                dates.append(p.published_date)
        dates.sort()
        try:
            vector_chunks = self._vector.count()
        except Exception:
            vector_chunks = 0
        return {
            "total_papers": len(papers),
            "by_source": sources,
            "oldest": dates[0] if dates else None,
            "newest": dates[-1] if dates else None,
            "vector_chunks": vector_chunks,
        }

    def to_summaries(self, papers: list[Paper]) -> list[PaperSummary]:
        return [PaperSummary.from_paper(p) for p in papers]

    # --- Internal ---

    def _upsert_vector(self, paper: Paper) -> None:
        text = paper.brief or paper.full_text or paper.abstract
        if not text:
            return
        try:
            self._vector.add(paper)
        except Exception as e:
            logger.warning("Vector upsert failed for %s: %s", paper.id, e)
