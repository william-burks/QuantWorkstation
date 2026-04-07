# Story 2 — SUPERSEDED_BY Relationship

## ID
QWS-0802

## Status
draft

## Blocked On
None (independent of QWS-0801)

## Summary
At Champion promotion time, create a `SUPERSEDED_BY` edge from the displaced Champion
to the new Champion. Enables single-hop lineage queries: "what replaced this strategy?"
without traversing the full Strategy → Champion chain.

## Problem
When a new Run is promoted and displaces the existing Champion, the old Champion becomes
a RetiredChampion via the existing `WAS_CHAMPION` edge. The link between the old Champion
and its replacement is only reachable by:

```
(RetiredChampion) ← [WAS_CHAMPION] ← (Champion)  -- current displacement chain
                                         ↓
                              [PRODUCED_CHAMPION]  -- hop to Strategy
                                   ↓
                               (Strategy)
                                   ↓
                              [PRODUCED_CHAMPION]  -- back to new Champion
                                   ↓
                          (New Champion)
```

Four hops. For lineage queries like "what is the successor of champion X?" this is
unnecessarily indirect. `SUPERSEDED_BY` provides the direct one-hop link.

Additionally, when a Champion is replaced by a better version of the SAME idea (as opposed
to OOS failure), there is currently no way to query "is this strategy a generational
improvement of an older approach, or a brand new direction?"

## Goal
At promotion time, `store.promote_to_champion()` creates a `SUPERSEDED_BY` edge from the
current Champion to the incoming Champion (before the current Champion is relabeled as
RetiredChampion):

```cypher
MATCH (old:Champion {champion_id: $old_id})
MATCH (new:Champion {champion_id: $new_id})
MERGE (old)-[:SUPERSEDED_BY]->(new)
```

No new CLI command is needed — this happens automatically as part of the existing promotion
path.

## Schema

### New edge
| Edge | Source → Target | Properties |
|---|---|---|
| `SUPERSEDED_BY` | Champion → Champion | none (the displaced champion IS the source) |

**Note:** The edge is created before the WAS_CHAMPION relabeling. After promotion
completes, the source node will have the `:RetiredChampion` label, but the edge
remains traversable as `(RetiredChampion)-[:SUPERSEDED_BY]->(Champion)`.

## Design

### Promotion path modification
Current flow in `store.promote_to_champion()`:
1. Create new Champion node
2. Relabel old Champion → RetiredChampion (MERGE new label, remove old)
3. Create `WAS_CHAMPION` edge

New flow:
1. Create new Champion node
2. **Create `SUPERSEDED_BY` edge from old Champion to new Champion**
3. Relabel old Champion → RetiredChampion
4. Create `WAS_CHAMPION` edge

The SUPERSEDED_BY edge is created in the same transaction as the relabeling.

### When SUPERSEDED_BY is NOT created
- First promotion for a Strategy (no existing Champion to displace) — no edge.
- `qw degrade` path (Champion → FormerChampion) — no edge; that is the decay path,
  not the replacement path.

## In Scope
- `qws_graph/research/graph/store.py` — add SUPERSEDED_BY edge creation inside the
  existing `promote_to_champion()` transaction
- `qws_graph/docs/data_dictionary.yaml` — document SUPERSEDED_BY edge
- `qws_graph/docs/graph_v1_contract.md` — add edge to schema section
- Unit tests: promotion with existing champion creates edge; first promotion creates no edge

## Out of Scope
- New CLI commands (promotion path is unchanged from the user's perspective)
- Query presets (lineage presets can be extended in a separate story if needed)
- Backfilling SUPERSEDED_BY edges on existing RetiredChampion nodes

## Repo Touchpoints
- `qws_graph/research/graph/store.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_store_dedup.py` (extend existing promotion tests)

## Acceptance Criteria
- [ ] Promoting a Run when a Champion already exists creates a `SUPERSEDED_BY` edge
  from the old Champion (now RetiredChampion) to the new Champion.
- [ ] Promoting a Run when no Champion exists (first promotion) creates no `SUPERSEDED_BY`
  edge.
- [ ] The SUPERSEDED_BY edge is traversable after the relabeling:
  `MATCH (r:RetiredChampion)-[:SUPERSEDED_BY]->(c:Champion)` returns the pair.
- [ ] Existing `WAS_CHAMPION` edge still created correctly alongside SUPERSEDED_BY.
- [ ] Unit tests cover: promotion with existing champion, first promotion, idempotent
  re-promotion (same run_id promoted twice).

## Definition of Done
- [ ] SUPERSEDED_BY edge created atomically within the existing promotion transaction.
- [ ] Edge traversable post-relabeling.
- [ ] Unit tests green.
- [ ] `data_dictionary.yaml` and `graph_v1_contract.md` updated.
- [ ] Story marked CLOSED.
- [ ] All affected README files updated to reflect new capabilities.
- [ ] PROVENANCE_ENGINE.md updated — SUPERSEDED_BY moved from `[TARGET]` to `[CURRENT]`.