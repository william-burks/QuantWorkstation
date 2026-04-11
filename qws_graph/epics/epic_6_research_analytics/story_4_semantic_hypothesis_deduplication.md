# Story 4 — Semantic Hypothesis Deduplication

## ID
QWS-0604

## Status
TESTING

## Blocked On
QWS-0601 (Hypothesis journaling must be CLOSED — Hypothesis nodes must exist before
SEMANTICALLY_RELATED edges can be created between them)

## Summary
When a new Hypothesis is recorded, compute cosine similarity against all existing
Hypothesis nodes using local embeddings. Create `SEMANTICALLY_RELATED` edges for pairs
exceeding the similarity threshold. Extends the `check_redundancy` surface to catch
same-idea hypotheses expressed in different words.

## Problem
`check_redundancy` (QWS-0601) checks for duplicate Hypothesis nodes but operates on
exact or fuzzy string match. The same underlying research idea can be expressed in many
different ways without triggering a match:

- "Tuesday London Open liquidity sweep in CL"
- "Morning session imbalance capitalizing on Asian session stops"

These two hypotheses may describe the same structural inefficiency. Without semantic
similarity checking, both get recorded, both lead to trial runs, and Will discovers
the duplication only when reviewing results — after the compute time was already spent.

`SEMANTICALLY_RELATED` edges let an LLM pre-query similar hypotheses before proposing a
new direction: `qw query --name similar_hypotheses --param hypothesis_id=<id>`.

## Goal
```zsh
# When a new hypothesis is recorded, similarity edges are auto-created:
qw record --hypothesis "Tuesday London Open liquidity sweep in CL"
# → creates Hypothesis node
# → computes similarity against all existing Hypothesis nodes
# → creates SEMANTICALLY_RELATED edges for pairs with similarity >= threshold
# → prints: "3 similar hypotheses found. Run: qw query --name similar_hypotheses --param hypothesis_id=<id>"

# Query similar hypotheses before proposing a direction:
qw query --name similar_hypotheses --param hypothesis_id=<id>
```

## Schema

### New edge
| Edge | Source ↔ Target | Properties |
|---|---|---|
| `SEMANTICALLY_RELATED` | Hypothesis ↔ Hypothesis | `similarity: float` (cosine, 0–1), `computed_at: datetime` |

The edge is symmetric: if A is semantically related to B, B is semantically related to A.
Implemented as two directed edges (A→B and B→A) for Cypher traversal simplicity.

### Threshold
Default: `0.85` cosine similarity. Configurable via `--similarity-threshold` flag on
`qw record --hypothesis`.

## Design

### Embedding model
Use a local embedding model — no external API calls (consistent with the research rules
prohibition on external LLM API calls). Default: `sentence-transformers/all-MiniLM-L6-v2`
(384-dim, fast, runs on CPU). The model is not stored in the graph — only the computed
similarity scores are stored as edge properties.

### Computation strategy
On each `qw record --hypothesis` call:
1. Embed the new hypothesis title.
2. Load all existing Hypothesis titles from the graph + their stored embedding vectors
   (if pre-computed), or compute on demand.
3. Compute cosine similarity against all existing nodes.
4. MERGE SEMANTICALLY_RELATED edges for pairs exceeding threshold.

To avoid recomputing all embeddings on every call, store the embedding vector on the
Hypothesis node as a `embedding: list[float]` property at creation time.

### New property on `:Hypothesis` (amendment to QWS-0601)
| Property | Type | Description |
|---|---|---|
| `embedding` | list[float] | Embedding vector of `title`, computed at creation time |

This property is additive — QWS-0601 nodes created before this story will have null
`embedding`. A backfill command (`qw backfill --embeddings`) is provided.

## In Scope
- `qws_graph/research/graph/store.py` — `set_hypothesis_embedding()`, `create_semantic_edges()`,
  `get_all_hypothesis_embeddings()` methods
- `qws_graph/research/graph/cli.py` — extend `qw record --hypothesis` to call embedding +
  edge creation; add `qw backfill --embeddings` for existing hypotheses
- `qws_graph/research/graph/query_presets.py` — `similar_hypotheses` preset filtered by
  `hypothesis_id`, returning title, similarity score, status of matched hypotheses
- `qws_graph/research/graph/query_presets.py` — extend `check_redundancy` to read
  `SEMANTICALLY_RELATED` edges in addition to string-match when edges exist
- `qws_graph/docs/data_dictionary.yaml` — SEMANTICALLY_RELATED edge, `embedding` property
  on Hypothesis
- `qws_graph/docs/graph_v1_contract.md` — add edge and property to schema section
- Unit tests: embedding computation, similarity threshold filter, symmetric edge creation,
  backfill command, null-safe handling for pre-existing hypotheses without embeddings

## Out of Scope
- Storing raw embedding vectors in a vector database (Neo4j property storage is sufficient
  at this scale)
- Cross-node type similarity (e.g., Hypothesis ↔ Strategy matching)
- Automatic hypothesis deduplication or merging

## Repo Touchpoints
- `qws_graph/research/graph/store.py`
- `qws_graph/research/graph/cli.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_store_semantic.py` — new
- `qws_graph/tests/unit/test_qw_hypothesis_similarity.py` — new

## Acceptance Criteria
- [x] `qw record --hypothesis "..."` embeds the title and stores the vector on the
  Hypothesis node at creation time.
- [x] After recording, SEMANTICALLY_RELATED edges are created for all existing Hypothesis
  nodes with cosine similarity >= threshold (default 0.85).
- [x] Edges are symmetric: if A→B exists, B→A also exists with the same `similarity` value.
- [x] `qw record --hypothesis "..." --similarity-threshold 0.90` uses 0.90 as the cutoff.
- [x] `qw query --name similar_hypotheses --param hypothesis_id=<id>` returns matched
  hypotheses ordered by similarity descending, with `title`, `similarity`, `status`.
- [x] `qw backfill --embeddings` embeds and stores vectors for all Hypothesis nodes that
  have null `embedding`, and creates any missing SEMANTICALLY_RELATED edges.
- [x] A Hypothesis with no similar counterparts produces no edges and no error.
- [x] Unit tests cover: above-threshold pair creates edges, below-threshold creates none,
  symmetric edge creation, backfill on existing null-embedding nodes.
- [x] `qw query --name check_redundancy --param hypothesis_id=<id>` surfaces
  SEMANTICALLY_RELATED hypotheses (similarity >= threshold) alongside string-match results
  when SEMANTICALLY_RELATED edges exist.

## Acceptance Test Plan

### AC1: qw record --hypothesis embeds and stores vector
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_record_hypothesis_embeds_and_stores_embedding -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC2: SEMANTICALLY_RELATED edges created above threshold
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_store_semantic.py::test_create_semantic_edges_above_threshold_creates_pair -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC3: Edges symmetric (A→B and B→A with same similarity)
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_store_semantic.py::test_create_semantic_edges_symmetric_pair_key -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: --similarity-threshold 0.90 forwarded correctly
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_record_hypothesis_custom_similarity_threshold -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: similar_hypotheses preset returns matches ordered by similarity
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_similar_hypotheses_preset_delegates_to_service -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC6: qw backfill --embeddings processes null-embedding nodes
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_backfill_embeddings_processes_null_embedding_nodes -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC7: No similar counterparts → no edges, no error
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_store_semantic.py::test_create_semantic_edges_empty_existing_returns_zero qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_record_hypothesis_no_advisory_when_no_similar -v`
- expect_contains: "2 passed"
- expect_exit: 0

### AC8: Unit tests (above/below threshold, symmetric, backfill)
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_store_semantic.py qws_graph/tests/unit/test_qw_hypothesis_similarity.py -v`
- expect_contains: "23 passed"
- expect_exit: 0

### AC9: check_redundancy includes semantic_matches
- type: cli
- cmd: `python -m pytest qws_graph/tests/unit/test_qw_hypothesis_similarity.py::test_check_redundancy_preset_routes_to_service -v`
- expect_contains: "PASSED"
- expect_exit: 0

## Definition of Done
- [x] Embedding computation, edge creation, and `similar_hypotheses` preset implemented
  and tested.
- [x] `qw backfill --embeddings` operational for existing hypothesis nodes.
- [x] `data_dictionary.yaml` and `graph_v1_contract.md` updated.
- [ ] Story marked CLOSED.
- [x] All affected README files updated to reflect new capabilities.
- [x] PROVENANCE_ENGINE.md updated — SEMANTICALLY_RELATED moved from `[TARGET]` to
  `[CURRENT]`; `embedding` property added to Hypothesis node spec.
