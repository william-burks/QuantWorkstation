from __future__ import annotations

import logging
from pathlib import Path

from qws_researcher import Paper

logger = logging.getLogger(__name__)

_CHUNK_CHARS = 512 * 4  # ~512 tokens @ 4 chars/token
_OVERLAP_CHARS = 64 * 4  # ~64 token overlap
_COLLECTION_NAME = "papers"


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunks = []
    current_chars = 0
    current_words: list[str] = []

    for word in words:
        current_words.append(word)
        current_chars += len(word) + 1

        if current_chars >= _CHUNK_CHARS:
            chunks.append(" ".join(current_words))
            # Overlap: keep last N chars worth of words
            overlap_words = []
            overlap_chars = 0
            for w in reversed(current_words):
                overlap_chars += len(w) + 1
                if overlap_chars > _OVERLAP_CHARS:
                    break
                overlap_words.insert(0, w)
            current_words = overlap_words
            current_chars = sum(len(w) + 1 for w in current_words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


class VectorIndex:
    def __init__(self, data_dir: str = "data") -> None:
        self._data_dir = data_dir
        self._client = None
        self._collection = None
        self._model = None

    def _ensure_initialized(self) -> None:
        if self._collection is not None:
            return

        import chromadb  # noqa: PLC0415
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        chroma_path = Path(self._data_dir) / "chroma"
        chroma_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(chroma_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.debug("VectorIndex initialized at %s", chroma_path)

    def add(self, paper: Paper) -> None:
        """Chunk paper text (or abstract), embed, and upsert into ChromaDB."""
        self._ensure_initialized()

        text = paper.full_text or paper.abstract
        if not text:
            return

        chunks = _chunk_text(text)
        if not chunks:
            return

        embeddings = self._model.encode(chunks, show_progress_bar=False).tolist()  # type: ignore[union-attr]

        ids = [f"{paper.id}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"paper_id": paper.id, "chunk_index": i} for i in range(len(chunks))]

        self._collection.upsert(  # type: ignore[union-attr]
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

    def search(self, query: str, n: int = 10) -> list[tuple[str, float]]:
        """
        Search by query string. Returns list of (paper_id, score) deduped by paper_id.
        Score is the best (lowest) distance for that paper.
        """
        self._ensure_initialized()

        collection_count = self._collection.count()  # type: ignore[union-attr]
        if collection_count == 0:
            return []

        query_embedding = self._model.encode([query], show_progress_bar=False).tolist()[0]  # type: ignore[union-attr]

        raw = self._collection.query(  # type: ignore[union-attr]
            query_embeddings=[query_embedding],
            n_results=min(n * 5, collection_count),
            include=["metadatas", "distances"],
        )

        return _dedup_results(raw, n)

    def search_similar(self, paper_id: str, n: int = 10) -> list[tuple[str, float]]:
        """Find papers similar to the given paper_id using its stored chunks."""
        self._ensure_initialized()

        # Get all chunks for this paper
        existing = self._collection.get(  # type: ignore[union-attr]
            where={"paper_id": paper_id},
            include=["embeddings"],
        )

        embeddings = existing.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return []

        # Average the chunk embeddings as a paper-level embedding
        import numpy as np  # noqa: PLC0415

        arr = np.array(embeddings, dtype=float)
        paper_embedding = np.mean(arr, axis=0).tolist()

        collection_count = self._collection.count()  # type: ignore[union-attr]
        raw = self._collection.query(  # type: ignore[union-attr]
            query_embeddings=[paper_embedding],
            n_results=min(n * 5 + 10, collection_count),
            include=["metadatas", "distances"],
        )

        results = _dedup_results(raw, n + 1)
        # Exclude the paper itself
        return [(pid, score) for pid, score in results if pid != paper_id][:n]

    def delete(self, paper_id: str) -> None:
        """Remove all chunks for a paper from the index."""
        self._ensure_initialized()

        existing = self._collection.get(where={"paper_id": paper_id})  # type: ignore[union-attr]
        if existing and existing.get("ids"):
            self._collection.delete(ids=existing["ids"])  # type: ignore[union-attr]

    def count(self) -> int:
        """Return the total number of chunks in the index."""
        self._ensure_initialized()
        return self._collection.count()  # type: ignore[union-attr]


def _dedup_results(raw: dict, n: int) -> list[tuple[str, float]]:
    """Deduplicate ChromaDB query results by paper_id, keeping best score per paper."""
    best: dict[str, float] = {}

    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    for meta, dist in zip(metadatas, distances):
        pid = meta["paper_id"]
        score = float(
            1.0 - dist
        )  # convert cosine distance to similarity; cast to avoid numpy ambiguity
        if pid not in best or score > best[pid]:
            best[pid] = score

    return sorted(best.items(), key=lambda x: x[1], reverse=True)[:n]
