***

# Spike — Lean Neighborhood Optimization

## ID
## QWS-0205C

**Status:** CLOSED  
**Priority:** **P1 — Risk Mitigation.** **Context:** A successful strategy generates thousands of `Run` nodes via grid sweeps. Without bounding `get_context_neighborhood` before ingestion scales, the system faces MCP context overflow and query timeouts.

---

## 1. Problem Statement
`get_context_neighborhood(champion_id)` currently returns the full relational fan-out: champion details, strategy summary, and the pivot run's configuration. While safe at low volumes, grid-search expansion will cause:
* **Token Overflow:** 1,000-run strategies exceed LLM context windows.
* **Query Latency:** Unbounded `MATCH` traversals degrade under load.
* **Context Drowning:** High-value signals (the Champion) are buried in low-value noise (redundant runs).

---

## 2. The Primary Research Direction: Option D (Curated Families)
**Mechanism:** Transition the graph from a **Raw Ledger** to a **Curated Knowledge Base**. This approach moves the complexity from the *query* layer to the *ingestion* layer.

### The Three-Pillar Implementation:
1.  **Significance Filtering (Ingestion):** Define "Significant" run criteria at the point of `qw record`:
    * **Performance:** Top-N by Sharpe within a family.
    * **Risk:** Bottom-N by Max Drawdown (instructional failure cases).
    * **Provenance:** Any run producing a Champion or flagged as `--significant` by the operator.
2.  **Structural Families:** Group by `logic_type + direction + source_hash`. Correlation queries operate on "Families" rather than raw Strategy IDs.
3.  **State Transitions (Orphaned vs. Aborted):**
    * **Orphaned:** Valid runs not yet promoted; visible in neighborhoods.
    * **Aborted:** Explicit "Death Certificates" explaining why a logic family was abandoned.



### Why this is the Strategic Choice:
Unlike truncation (hiding data), this **adds meaning**. It allows the MCP to perform **Reasoning Recovery**—understanding not just what worked, but why specific "Paths Not Taken" were rejected.

---

## 3. Recommended Implementation Roadmap

| Horizon | Strategy | Action |
| :--- | :--- | :--- |
| **Now (V1 Patch)** | **Option A (The Cap)** | Apply `max_results=50` safety cap to `get_context_neighborhood`. Prevents immediate overflow with zero breaking changes. |
| **Near-term (V1.5)** | **Option C (The Roll-up)** | Add an `aggregation` mode to Cypher. Returns a `RunStatsSummaryV1` DTO (Avg Sharpe, Total Vol) instead of raw nodes. |
| **Strategic (V2)** | **Option D (The Curator)** | Full implementation of **Significance Filtering** and **Family Definitions**. This is the terminal state for research scale. |

---

## 4. Spike Output (Definition of Done)
- [x] **Immediate:** V1 safety cap implemented in `mcp_adapter.py` — `get_context_neighborhood(champion_id, max_runs=50)` with `max_runs` validated in 1..200; `runs_capped` flag returned; 42 unit tests passing. Follow-on story drafted at `epics/unsorted_stories/story_recursive_lineage_traversal.md`.
- [x] **Architecture:** Option D dependencies linked to `epics/unsorted_stories/story_strategy_family_definitions.md` (P2 — family taxonomy, `family_id` spec, V2 migration path).
- [x] **Documentation:** Neighborhood bounding contract documented in `docs/graph_v1_contract.md` § MCP Read Contract V1 → "Neighborhood Bounding (V1 Safety Cap)".

## 5. Repo Touchpoints
* `research/graph/mcp_adapter.py`: Update `get_context_neighborhood` signature to handle limits.
* `research/graph/query.py`: Implement new `aggregation` Cypher logic for Option C.
* `docs/graph_v1_contract.md`: Define the "Significance" rules for V2 ingestion.

## 6. Open Questions for implementation
1.  Is `max_results=50` the right heuristic for a single LLM turn, or should it be an ENV var?
2.  Should the `--significant` flag be manual at `qw record` or an automated post-process pass?
3.  How do we handle "Legacy Noise" (bulk data ingested before the Curator rules were active)?
