# Story N — <Title>

## ID
QWS-XXXX

## Status
DRAFT

## Type
schema

## Blocked On
<QWS-XXXX | None>

## Summary
<One sentence. What schema element is added and why.>

## Problem
<What query or workflow is impossible without this schema change.>

## Goal
<What becomes queryable or expressible after this story is closed.>

## Schema Extension
| Element | Type | Properties | Notes |
|---|---|---|---|
| `NODE_TYPE` | Node | `prop: type` | new |
| `EDGE_TYPE` | Edge | Source → Target | new |

All additions must be registered in `qws_graph/docs/data_dictionary.yaml`.

## In Scope
<Exact schema additions. Exact Cypher migration if needed.>

## Out of Scope
<Explicit exclusions — e.g. "no query presets in this story".>

## Repo Touchpoints
<!-- MAX 5 FILES. If you need more, split the story. -->
- `qws_graph/docs/data_dictionary.yaml` — schema registration
- `qws_graph/research/graph/store.py` — new write method if needed
- `qws_graph/tests/unit/test_<feature>.py` — new

## Acceptance Criteria
- [ ] <Binary. Node/edge queryable via Cypher. Property present on node.>

## Definition of Done
- [ ] data_dictionary.yaml updated
- [ ] Tests green
- [ ] Story marked CLOSED