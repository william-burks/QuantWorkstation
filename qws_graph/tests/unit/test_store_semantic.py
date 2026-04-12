"""Unit tests for semantic hypothesis deduplication (QWS-0604).

Tests cover:
- create_semantic_edges: above-threshold pair creates edges
- create_semantic_edges: below-threshold creates none
- create_semantic_edges: symmetric pair_key logic
- create_semantic_edges: null-safe exclusion of null-embedding nodes
- set_hypothesis_embedding: delegates to correct Cypher
- get_all_hypothesis_embeddings: returns rows with embedding key
- get_hypotheses_without_embeddings: returns rows without embedding
- cosine similarity math (via store internals)
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

from research.graph.store import GraphStore

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_store() -> GraphStore:
    with patch("research.graph.store.GraphDatabase.driver"):
        return GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")


def _unit_vec(dim: int, index: int) -> list[float]:
    """Return a unit vector in the given dimension with a 1.0 at *index*."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


def _similar_vecs(dim: int = 8) -> tuple[list[float], list[float]]:
    """Two nearly-identical vectors (cosine ~0.999)."""
    base = [1.0 / math.sqrt(dim)] * dim
    perturb = base[:]
    perturb[0] += 0.001
    norm = math.sqrt(sum(x * x for x in perturb))
    perturb = [x / norm for x in perturb]
    return base, perturb


def _orthogonal_vecs(dim: int = 8) -> tuple[list[float], list[float]]:
    """Two orthogonal unit vectors (cosine == 0.0)."""
    return _unit_vec(dim, 0), _unit_vec(dim, 1)


# ── set_hypothesis_embedding ─────────────────────────────────────────────────


def test_set_hypothesis_embedding_calls_cypher() -> None:
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    # execute_write returns list of records (non-empty = found)
    mock_session.execute_write = MagicMock(return_value=[{"hypothesis_id": "abc123"}])
    store._driver.session = MagicMock(return_value=mock_session)

    result = store.set_hypothesis_embedding("abc123", [0.1, 0.2, 0.3])
    assert result is True
    mock_session.execute_write.assert_called_once()


def test_set_hypothesis_embedding_returns_false_when_not_found() -> None:
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock(return_value=[])
    store._driver.session = MagicMock(return_value=mock_session)

    result = store.set_hypothesis_embedding("missing_id", [0.1])
    assert result is False


# ── get_all_hypothesis_embeddings ────────────────────────────────────────────


def test_get_all_hypothesis_embeddings_returns_rows() -> None:
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    rows = [
        {"hypothesis_id": "aaa111", "title": "Title A", "embedding": [0.1, 0.2]},
        {"hypothesis_id": "bbb222", "title": "Title B", "embedding": [0.3, 0.4]},
    ]
    mock_session.execute_read = MagicMock(return_value=rows)
    store._driver.session = MagicMock(return_value=mock_session)

    result = store.get_all_hypothesis_embeddings()
    assert len(result) == 2
    assert result[0]["hypothesis_id"] == "aaa111"
    assert result[1]["embedding"] == [0.3, 0.4]


# ── get_hypotheses_without_embeddings ────────────────────────────────────────


def test_get_hypotheses_without_embeddings_returns_rows() -> None:
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    rows = [{"hypothesis_id": "ccc333", "title": "Old hypothesis with no embedding"}]
    mock_session.execute_read = MagicMock(return_value=rows)
    store._driver.session = MagicMock(return_value=mock_session)

    result = store.get_hypotheses_without_embeddings()
    assert len(result) == 1
    assert result[0]["hypothesis_id"] == "ccc333"


# ── create_semantic_edges ────────────────────────────────────────────────────


def test_create_semantic_edges_above_threshold_creates_pair() -> None:
    """Two similar vectors → 1 pair created (= 2 directed edges)."""
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock(return_value=None)
    store._driver.session = MagicMock(return_value=mock_session)

    v_a, v_b = _similar_vecs()
    existing = [{"hypothesis_id": "existing_001", "title": "Similar", "embedding": v_b}]

    n_pairs = store.create_semantic_edges(
        new_hypothesis_id="new_aaa111",
        new_embedding=v_a,
        existing_embeddings=existing,
        threshold=0.85,
    )

    assert n_pairs == 1
    mock_session.execute_write.assert_called_once()


def test_create_semantic_edges_below_threshold_creates_none() -> None:
    """Orthogonal vectors (cosine=0) → 0 pairs, no Neo4j write."""
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock(return_value=None)
    store._driver.session = MagicMock(return_value=mock_session)

    v_a, v_b = _orthogonal_vecs()
    existing = [{"hypothesis_id": "existing_001", "title": "Orthogonal", "embedding": v_b}]

    n_pairs = store.create_semantic_edges(
        new_hypothesis_id="new_aaa111",
        new_embedding=v_a,
        existing_embeddings=existing,
        threshold=0.85,
    )

    assert n_pairs == 0
    mock_session.execute_write.assert_not_called()


def test_create_semantic_edges_empty_existing_returns_zero() -> None:
    """No existing embeddings → 0 pairs, no write."""
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock()
    store._driver.session = MagicMock(return_value=mock_session)

    n_pairs = store.create_semantic_edges(
        new_hypothesis_id="new_aaa111",
        new_embedding=[1.0, 0.0],
        existing_embeddings=[],
        threshold=0.85,
    )

    assert n_pairs == 0
    mock_session.execute_write.assert_not_called()


def test_create_semantic_edges_excludes_self() -> None:
    """When new_hypothesis_id matches an entry in existing_embeddings, skip it."""
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock()
    store._driver.session = MagicMock(return_value=mock_session)

    v_a = [1.0, 0.0]
    existing = [
        {"hypothesis_id": "new_aaa111", "title": "Same node", "embedding": v_a},  # self — skip
    ]

    n_pairs = store.create_semantic_edges(
        new_hypothesis_id="new_aaa111",
        new_embedding=v_a,
        existing_embeddings=existing,
        threshold=0.50,
    )

    assert n_pairs == 0
    mock_session.execute_write.assert_not_called()


def test_create_semantic_edges_symmetric_pair_key() -> None:
    """pair_key must be sorted alphabetically regardless of which node is 'new'."""
    store = _make_store()
    captured_pairs: list[dict] = []

    def _capture_write(fn):  # type: ignore[no-untyped-def]
        # fn is the lambda passed to execute_write; call it with a dummy tx
        class _FakeTx:
            def run(self, query: str, **kwargs: object) -> MagicMock:
                captured_pairs.extend(kwargs.get("pairs", []))  # type: ignore[arg-type]
                return MagicMock()

        fn(_FakeTx())

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock(side_effect=_capture_write)
    store._driver.session = MagicMock(return_value=mock_session)

    v_a, v_b = _similar_vecs()
    # "zzz999" sorts after "aaa111" → pair_key must be "aaa111|zzz999"
    existing = [{"hypothesis_id": "aaa111", "title": "Alpha", "embedding": v_b}]

    store.create_semantic_edges(
        new_hypothesis_id="zzz999",
        new_embedding=v_a,
        existing_embeddings=existing,
        threshold=0.85,
    )

    assert len(captured_pairs) == 1
    assert captured_pairs[0]["pair_key"] == "aaa111|zzz999"
    assert captured_pairs[0]["hypothesis_id_a"] == "aaa111"
    assert captured_pairs[0]["hypothesis_id_b"] == "zzz999"


def test_create_semantic_edges_custom_threshold() -> None:
    """Custom threshold=0.50 accepts pairs that 0.85 would reject."""
    store = _make_store()
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute_write = MagicMock(return_value=None)
    store._driver.session = MagicMock(return_value=mock_session)

    # cosine ~0.707 (45-degree angle)
    v_a = [1.0 / math.sqrt(2), 1.0 / math.sqrt(2)]
    v_b = [1.0, 0.0]
    existing = [{"hypothesis_id": "existing_001", "title": "Moderate", "embedding": v_b}]

    n_high = store.create_semantic_edges("new_001", v_a, existing, threshold=0.85)
    assert n_high == 0  # 0.707 < 0.85

    mock_session.execute_write.reset_mock()

    n_low = store.create_semantic_edges("new_001", v_a, existing, threshold=0.50)
    assert n_low == 1  # 0.707 >= 0.50
