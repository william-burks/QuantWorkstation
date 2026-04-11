"""Unit tests for semantic hypothesis deduplication CLI (QWS-0604).

Tests cover:
- qw record --hypothesis embeds title, stores embedding on node
- advisory message when similar hypotheses found
- no advisory when no similar hypotheses
- ImportError from sentence-transformers is non-fatal (WARNING on stderr, exit 0)
- --similarity-threshold 0.90 forwarded to create_semantic_edges
- qw backfill --embeddings processes null-embedding nodes
- similar_hypotheses preset routes to correct view function
- check_redundancy preset includes semantic_matches key in output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import (  # noqa: E402
    _cmd_hypothesis,
    _DEFAULT_SIMILARITY_THRESHOLD,
    cmd_backfill,
)
from research.graph.query_presets import PRESET_CATALOG, resolve_preset, run_preset, validate_params  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_hypothesis_args(
    hypothesis: str = "Test hypothesis title",
    tested_as: str | None = None,
    branched_from: str | None = None,
    rationale: str | None = None,
    status: str | None = None,
    timeout_seconds: int = 3,
    similarity_threshold: float | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        hypothesis=hypothesis,
        tested_as=tested_as,
        branched_from=branched_from,
        rationale=rationale,
        status=status,
        timeout_seconds=timeout_seconds,
        similarity_threshold=similarity_threshold,
    )


def _make_backfill_args(
    embeddings: bool = True,
    timeout_seconds: int = 3,
    similarity_threshold: float | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        embeddings=embeddings,
        timeout_seconds=timeout_seconds,
        similarity_threshold=similarity_threshold,
    )


def _mock_store(
    existing_embeddings: list[dict] | None = None,
    n_similar: int = 0,
    without_embeddings: list[dict] | None = None,
) -> MagicMock:
    store = MagicMock()
    store.create_hypothesis = MagicMock()
    store.set_hypothesis_embedding = MagicMock(return_value=True)
    store.get_all_hypothesis_embeddings = MagicMock(return_value=existing_embeddings or [])
    store.get_hypotheses_without_embeddings = MagicMock(return_value=without_embeddings or [])
    store.create_semantic_edges = MagicMock(return_value=n_similar)
    store.close = MagicMock()
    return store


# ── qw record --hypothesis (create mode) ────────────────────────────────────


def test_record_hypothesis_embeds_and_stores_embedding(capsys: pytest.CaptureFixture) -> None:
    """Creating a hypothesis embeds the title and stores the vector."""
    fake_embedding = [0.1] * 384
    store = _mock_store(existing_embeddings=[], n_similar=0)

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch("research.graph.cli._embed_text", return_value=fake_embedding) as mock_embed,
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_hypothesis_args(hypothesis="Bear market liquidity sweep in CL")
        exit_code = _cmd_hypothesis(args)

    assert exit_code == 0
    mock_embed.assert_called_once_with("Bear market liquidity sweep in CL")
    store.set_hypothesis_embedding.assert_called_once()
    call_args = store.set_hypothesis_embedding.call_args
    assert call_args[0][1] == fake_embedding  # embedding passed correctly


def test_record_hypothesis_prints_advisory_when_similar_found(capsys: pytest.CaptureFixture) -> None:
    """When n_similar > 0, advisory message printed to stdout."""
    store = _mock_store(n_similar=2)

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch("research.graph.cli._embed_text", return_value=[0.5] * 384),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_hypothesis_args(hypothesis="Morning session liquidity grab on ES")
        exit_code = _cmd_hypothesis(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "2 similar hypotheses found" in captured.out
    assert "similar_hypotheses" in captured.out


def test_record_hypothesis_no_advisory_when_no_similar(capsys: pytest.CaptureFixture) -> None:
    """When n_similar == 0, no advisory message."""
    store = _mock_store(n_similar=0)

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch("research.graph.cli._embed_text", return_value=[0.1] * 384),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_hypothesis_args(hypothesis="Totally unique research direction")
        exit_code = _cmd_hypothesis(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "similar hypotheses found" not in captured.out


def test_record_hypothesis_embedding_import_error_is_non_fatal(capsys: pytest.CaptureFixture) -> None:
    """ImportError from sentence-transformers is non-fatal: exit 0, WARNING on stderr."""
    store = _mock_store()

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch(
            "research.graph.cli._embed_text",
            side_effect=ImportError("sentence-transformers not installed"),
        ),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_hypothesis_args(hypothesis="Hypothesis that cannot be embedded")
        exit_code = _cmd_hypothesis(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "sentence-transformers" in captured.err
    # Hypothesis was still created in the graph
    store.create_hypothesis.assert_called_once()
    # Embedding was NOT stored (exception before set_hypothesis_embedding)
    store.set_hypothesis_embedding.assert_not_called()


def test_record_hypothesis_custom_similarity_threshold(capsys: pytest.CaptureFixture) -> None:
    """--similarity-threshold 0.90 is forwarded to create_semantic_edges."""
    store = _mock_store(n_similar=0)

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch("research.graph.cli._embed_text", return_value=[0.3] * 384),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_hypothesis_args(hypothesis="Custom threshold test", similarity_threshold=0.90)
        exit_code = _cmd_hypothesis(args)

    assert exit_code == 0
    call_kwargs = store.create_semantic_edges.call_args[1]
    assert call_kwargs.get("threshold") == pytest.approx(0.90)


# ── qw backfill --embeddings ─────────────────────────────────────────────────


def test_backfill_embeddings_processes_null_embedding_nodes(capsys: pytest.CaptureFixture) -> None:
    """backfill embeds nodes with null embedding and calls create_semantic_edges."""
    targets = [
        {"hypothesis_id": "old_001", "title": "Old hypothesis A"},
        {"hypothesis_id": "old_002", "title": "Old hypothesis B"},
    ]
    all_embs = [
        {"hypothesis_id": "old_001", "title": "Old hypothesis A", "embedding": [0.1] * 384},
        {"hypothesis_id": "old_002", "title": "Old hypothesis B", "embedding": [0.2] * 384},
    ]
    store = _mock_store(without_embeddings=targets)
    store.get_all_hypothesis_embeddings = MagicMock(return_value=all_embs)

    # Patch the import check inside cmd_backfill so sentence-transformers need not be installed.
    import importlib
    fake_st_module = MagicMock()
    fake_st_module.SentenceTransformer = MagicMock()

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch("research.graph.cli._embed_text", return_value=[0.1] * 384),
        patch.dict("sys.modules", {"sentence_transformers": fake_st_module}),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_backfill_args(embeddings=True)
        exit_code = cmd_backfill(args)

    assert exit_code == 0
    assert store.set_hypothesis_embedding.call_count == 2
    captured = capsys.readouterr()
    assert "backfill complete" in captured.out


def test_backfill_embeddings_no_targets_exits_cleanly(capsys: pytest.CaptureFixture) -> None:
    """When all hypotheses already have embeddings: 0 processed, exit 0."""
    store = _mock_store(without_embeddings=[])

    fake_st_module = MagicMock()
    fake_st_module.SentenceTransformer = MagicMock()

    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch("research.graph.cli.GraphStore.from_env", return_value=store),
        patch.dict("sys.modules", {"sentence_transformers": fake_st_module}),
    ):
        MockConnector.return_value.is_available.return_value = True
        args = _make_backfill_args(embeddings=True)
        exit_code = cmd_backfill(args)

    assert exit_code == 0
    store.set_hypothesis_embedding.assert_not_called()
    captured = capsys.readouterr()
    assert "0 hypotheses" in captured.out


def test_backfill_requires_embeddings_flag(capsys: pytest.CaptureFixture) -> None:
    """qw backfill without --embeddings returns exit code 1."""
    args = _make_backfill_args(embeddings=False)
    exit_code = cmd_backfill(args)
    assert exit_code == 1


def test_backfill_neo4j_unavailable_returns_2() -> None:
    fake_st_module = MagicMock()
    fake_st_module.SentenceTransformer = MagicMock()
    with (
        patch("research.graph.cli.NeoConnector") as MockConnector,
        patch.dict("sys.modules", {"sentence_transformers": fake_st_module}),
    ):
        MockConnector.return_value.is_available.return_value = False
        args = _make_backfill_args(embeddings=True)
        exit_code = cmd_backfill(args)
    assert exit_code == 2


# ── similar_hypotheses preset ────────────────────────────────────────────────


def test_similar_hypotheses_preset_in_catalog() -> None:
    """similar_hypotheses preset exists in PRESET_CATALOG."""
    assert "similar_hypotheses" in PRESET_CATALOG
    spec = PRESET_CATALOG["similar_hypotheses"]
    param_names = {p.name for p in spec.params}
    assert "hypothesis_id" in param_names
    # hypothesis_id is required
    required = {p.name for p in spec.params if p.required}
    assert "hypothesis_id" in required


def test_similar_hypotheses_preset_validates_required_param() -> None:
    """Missing hypothesis_id raises validation error."""
    spec = resolve_preset("similar_hypotheses")
    errors = validate_params(spec, {})
    assert any("hypothesis_id" in e for e in errors)


def test_similar_hypotheses_preset_delegates_to_service(capsys: pytest.CaptureFixture) -> None:
    """run_preset routes similar_hypotheses to service.get_similar_hypotheses_v1."""
    mock_service = MagicMock()
    mock_service.get_similar_hypotheses_v1 = MagicMock(
        return_value=[{"hypothesis_id": "aaa111", "title": "Related", "similarity": 0.92, "status": "open"}]
    )

    results = run_preset("similar_hypotheses", {"hypothesis_id": "bbb222"}, service=mock_service)

    mock_service.get_similar_hypotheses_v1.assert_called_once_with(hypothesis_id="bbb222")
    assert len(results) == 1
    assert results[0]["similarity"] == 0.92


# ── check_redundancy preset (upgraded) ───────────────────────────────────────


def test_check_redundancy_preset_routes_to_service() -> None:
    """check_redundancy routes to service.get_check_redundancy_v1."""
    mock_service = MagicMock()
    mock_service.get_check_redundancy_v1 = MagicMock(
        return_value=[{
            "hypothesis_id": "ccc333",
            "title": "Test",
            "active_champion_matches": [],
            "aborted_strategy_matches": [],
            "semantic_matches": [{"hypothesis_id": "ddd444", "title": "Similar", "similarity": 0.88}],
        }]
    )

    results = run_preset("check_redundancy", {"hypothesis_id": "ccc333"}, service=mock_service)

    mock_service.get_check_redundancy_v1.assert_called_once_with(hypothesis_id="ccc333")
    assert len(results) == 1
    assert "semantic_matches" in results[0]
    assert results[0]["semantic_matches"][0]["similarity"] == 0.88
