# Spike — Lean Neighborhood Optimization

## Status
draft

## Priority
P1 — Risk Mitigation. A successful strategy will generate thousands of `Run` nodes from grid sweeps.
If `get_context_neighborhood` is not bounded before ingestion scales, it will overflow MCP context
windows and time out. This spike must produce a recommended design before ingestion volume grows.

## Problem Statement
`get_context_neighborhood(champion_id)` fans out to three view functions and returns everything
connected to a champion: champion details, strategy summary, and the pivot run's config. Today the
volume is small and the call is safe. As the graph grows — particularly via grid-search runs —
a single `Champion` may be connected to hundreds or thousands of `Run` nodes through `Strategy`.

Concrete failure modes:
- Token overflow: a 1,000-run strategy returns a neighborhood too large for an LLM context window.
- Query timeout: unbounded `MATCH` traversals over large graphs degrade under load.
- Context drowning: the MCP tool returns so much data that the useful signal (the champion itself)
  is buried in noise.

This spike evaluates options for bounding neighborhood size while preserving research utility.

## Goal
Identify the best trade-off strategy for keeping `get_context_neighborhood` lean and document
a recommended implementation path. No code is written during this spike; the output is a
decision record that becomes the implementation brief for the follow-on story.

## Inputs
- `research/graph/mcp_adapter.py` — current `get_context_neighborhood` implementation
- `research/graph/query.py` — `GET_RECENT_CHAMPIONS_V1_CYPHER` as a pattern for limit application
- `docs/graph_v1_contract.md` — V1 scope and canonical node/edge set
- `qws_graph/epics/unsorted_stories/spike_lean_neighborhood_optimization.md` (this document)

## Options Evaluated

### Option A — max_results Cap (Recent-First Truncation)
**Mechanism:** Hard-limit the `HAS_RUN` traversal to the `$N` most recent or `$N`
highest-performing runs before returning. Mirrors the `limit` pattern in `get_recent_champions_v1`.

**Implementation sketch:**
```cypher
MATCH (s:Strategy {strategy_id: $strategy_id})-[:HAS_RUN]->(r:Run)
WITH r ORDER BY r.timestamp DESC LIMIT $max_results
...
```

**Pros:**
- Guaranteed small JSON payload regardless of graph volume.
- Extremely fast query execution; no aggregation overhead.
- Trivial to add as a parameter with a safe default (e.g., `max_results=20`).
- Consistent with existing `limit` pattern in the query layer.

**Cons:**
- Loses historical perspective. An LLM cannot identify performance decay if older
  (and possibly better) runs are truncated.
- "Recent" is not always the most informative dimension — a run from 6 months ago
  with the highest Sharpe may be the most relevant context.
- Requires callers to know to ask for "more" if the default window is insufficient.

**Risk:** Low implementation risk; medium research-value risk at scale.

---

### Option B — Relationship Tiering (max_depth / Lazy Loading)
**Mechanism:** Return `Config` and `Champion` nodes by default (depth=1), but omit `Run`
detail rows unless the caller explicitly requests a second-level query.

**Implementation sketch:**
```python
# depth=1: champion + strategy summary only
# depth=2: adds pivot_config
# depth=3: adds full run history (separate tool call)
def get_context_neighborhood(champion_id, depth=2): ...
```

**Pros:**
- Initial "snapshot" payload is extremely small — suitable for quick orientation.
- Callers that need run detail make an explicit second call; those that don't, don't pay.
- Keeps `get_context_neighborhood` semantically focused on the champion node.

**Cons:**
- Increases chatty I/O. An agent may require 2–3 turns to gather enough evidence to answer
  a simple performance question ("is this champion better than the last one?").
- Depth semantics are subtle — depth=2 vs depth=3 requires callers to reason about graph topology.
- The "second call" is often `get_run_history`, which is already a separate tool;
  this option may just rename the existing pattern without solving the problem.

**Risk:** Low implementation risk; medium usability risk (chatty agents are expensive).

---

### Option C — Representative Aggregation (Stats Roll-Up)
**Mechanism:** Use Cypher aggregation to compress N runs into a single `StatsSummary` object
(e.g., `avg_sharpe`, `max_drawdown_volatility`, `p25/p50/p75 win_rate`) rather than returning
individual rows.

**Implementation sketch:**
```cypher
MATCH (s:Strategy)-[:HAS_RUN]->(r:Run)
RETURN {
  avg_sharpe: avg(r.sharpe),
  max_drawdown_floor: min(r.max_drawdown),
  run_count: count(r),
  best_run_id: ...
} AS run_summary
```

**Pros:**
- High "relational intelligence." Provides the conclusion without the noise.
- Payload size is O(1) regardless of run volume — scales perfectly.
- LLMs can reason over statistical summaries more reliably than raw row lists.

**Cons:**
- Increases complexity in the query layer; requires new Cypher aggregation patterns.
- Obscures individual outlier runs that may be the most instructive data points.
- Aggregates are lossy — the LLM cannot ask follow-up questions about specific runs
  without a second query.
- Premature: useful at 10,000 runs, possibly overkill at 100 runs.

**Risk:** Medium implementation risk; low payload risk; requires a new DTO.

---

### Option D — Curated Ingestion (Recommended Direction)
**Mechanism:** Shift from a raw ledger ("record everything") to a curated knowledge base
("record only instructive data"). Combine ingestion filtering with structural family grouping
and explicit state transitions.

**Three-part mechanism:**

1. **Ingestion Filtering:** Stop recording every grid-search iteration. Define "significant"
   run criteria at ingest time:
   - Top-N by Sharpe within a strategy family.
   - Bottom-N by max_drawdown (risk boundary / instructional failure cases).
   - Any run that produced a champion (always significant).
   - Any run flagged as `--significant` by the operator.

2. **Structural Families:** Group runs by `logic_type + direction + source_hash` (see
   `spike_strategy_family_definitions.md`). Correlation queries operate on families, not on
   raw strategy IDs, preventing the "junk drawer" problem.

3. **State Transitions — Orphaned vs. Aborted:**
   - `Orphaned`: A valid run not yet promoted to champion. Visible in neighborhood.
   - `Aborted`: An explicit "death certificate" node/status explaining why a specific logic
     family was abandoned. Visible as context; not as noise.

**Why this is the primary research direction:**
Unlike Options A–C, which hide data after the fact, Option D adds meaning before it enters
the graph. The "neighborhood" stays naturally lean because only instructive data survives
ingestion.

**Pros:**
- Reasoning recovery: the MCP can see the "path not taken." By seeing why a prior
  `Orphan` was `Aborted`, the researcher avoids repeating failed experiments.
- Signal-to-noise: the neighborhood is lean by construction, not by truncation.
- Cross-artifact intelligence: anchoring on families makes `get_cross_artifact_correlation_v1`
  trustworthy — you compare apples to apples.
- No query complexity increase; payload shrinks at the source.

**Cons:**
- Requires operator discipline at ingest time (the `--significant` flag or filtering logic).
- Retroactively hard to apply to already-ingested bulk runs without a migration.
- Adds schema complexity: `Aborted` state requires a new node property or edge type.
- Longer implementation horizon — this is a V2 architectural shift, not a V1 patch.

**Risk:** High design risk (requires schema changes); low long-term operational risk.

---

## Recommended Direction

| Horizon | Recommendation |
|---------|---------------|
| **Now (V1 patch)** | Apply Option A (`max_results=50`) as a default safety cap on `get_context_neighborhood`. Zero breaking changes; prevents overflow immediately. |
| **Near-term (V1.5)** | Add Option C aggregation as a `compact=true` mode alongside full output. Gives LLMs a summary path without removing raw access. |
| **Strategic (V2)** | Implement Option D (curated ingestion + family grouping). This is the architecture that makes the graph genuinely useful at research scale. |

The V1 patch (Option A cap) is the minimum viable safety measure and can be implemented
in the same PR as the follow-on story. Options C and D are sequenced after the
`spike_strategy_family_definitions.md` design decision is made.

## Spike Output (Definition of Done)

- [ ] This document reviewed and annotated with any repo-specific constraints.
- [ ] Option A (`max_results` default cap) approved for immediate implementation.
- [ ] Follow-on story written for V1 patch: "Add max_results safety cap to get_context_neighborhood."
- [ ] Option D implementation dependencies identified and linked to Epic 3 workflow stories.
- [ ] Decision recorded in `docs/` or ADR if architectural (e.g., `manage_adr` via codebase-memory-mcp).

## Repo Touchpoints (Anticipated)
- `research/graph/mcp_adapter.py` — `get_context_neighborhood` signature
- `research/graph/query.py` — potential new aggregation Cypher
- `research/graph/query_models.py` — potential `RunStatsSummaryV1` DTO (Option C)
- `docs/graph_v1_contract.md` — ingestion filtering rules (Option D)

## Open Questions
- What is the practical maximum number of `Run` nodes per `Strategy` in the current dataset?
- Is `max_results=50` an appropriate default, or should it be configurable from env?
- Should `Aborted` be a `Champion.oos_status` value or a separate node type?
- Does the `--significant` flag belong on `qw record` or in a post-ingest curation pass?

## Notes
Priority: **P1 — implement V1 safety cap before the next bulk ingestion run.**
This spike is a prerequisite for `story_strategy_family_definitions.md` (Option D depends
on family grouping) and blocks any MCP deployment at production ingestion volume.
