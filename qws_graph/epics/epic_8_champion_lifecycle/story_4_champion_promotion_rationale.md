# Story 4 — Champion Promotion Rationale

## ID
QWS-0805

## Status
DRAFT

## Blocked On
None

## Summary
Add a `promotion_rationale` property to the Champion node to capture why a strategy was
promoted. Expose it via `--rationale` flag on `qw champion`, include it in the
`recent_champions` query preset output, and seed realistic values in the demo seed.

## Problem
Champion nodes record performance metrics at promotion time but not the reasoning behind
the promotion decision. When reviewing `recent_champions` output, neither the researcher nor
the LLM can distinguish "promoted because it dominated all alternatives in the current
portfolio" from "promoted because it was the only candidate that week." Without explicit
rationale, the promotion history is metrics-only — no decision context survives the session.

## Goal

```zsh
# Manual promotion with rationale
qw champion --strategy btc-1h-trend-v3 --rationale "Only strategy to pass corr gate against CL; Sharpe 3.1 in high-vol regime"

# Auto-promotion gate (rationale optional — defaults to empty string)
qw champion --strategy es-1h-mean-rev --auto

# Query output now includes rationale
qw query --name recent_champions
# champion_id | strategy | sharpe | promotion_rationale
# abc123       | btc-1h   | 3.1    | Only strategy to pass corr gate...
```

## Schema
One new property on the `Champion` node:

| Property | Type | Nullable | Description |
|---|---|---|---|
| `promotion_rationale` | str | Yes (empty string acceptable) | Free-text explanation of why this strategy was promoted at the time of promotion |

No new nodes, edges, or relationships.

## In Scope
- `docs/PROVENANCE_ENGINE.md` — add `promotion_rationale` to Champion node property table
- `qws_graph/docs/data_dictionary.yaml` — add `promotion_rationale` field to Champion
- `research/graph/cli.py` — add `--rationale` flag to `qw champion` command; required for
  manual promotion paths, optional (defaults to `""`) for auto-gate path
- `research/graph/store.py` (or equivalent champion write path) — persist `promotion_rationale`
  on Champion MERGE block
- `qws_graph/cypher/presets/recent_champions.cypher` — include `c.promotion_rationale` in
  RETURN clause
- `qws_graph/seed/demo_seed.cypher` — add realistic `promotion_rationale` strings to all
  Champion MERGE blocks
- `docs/BACKLOG_ALIGNMENT.md` — add `promotion_rationale` to Champion row in Not Yet
  Implemented Properties table until this story is CLOSED

## Out of Scope
- Retroactive backfill of existing Champion nodes (field is nullable; empty string acceptable)
- Enforced minimum length or vocabulary for rationale text
- Rationale on RetiredChampion or FormerChampion nodes (those carry `oos_reason` /
  `retirement_note` instead)

## Repo Touchpoints
- `docs/PROVENANCE_ENGINE.md`
- `qws_graph/docs/data_dictionary.yaml`
- `research/graph/cli.py`
- `research/graph/store.py` (champion write path)
- `qws_graph/cypher/presets/recent_champions.cypher`
- `qws_graph/seed/demo_seed.cypher`
- `docs/BACKLOG_ALIGNMENT.md`

## Acceptance Criteria
- [ ] `promotion_rationale` documented in `docs/PROVENANCE_ENGINE.md` Champion node property
  table, marked nullable
- [ ] `qw champion --strategy <id> --rationale "<text>"` stores rationale on the Champion node
- [ ] `qw champion` without `--rationale` on a manual promotion path raises a validation error
  prompting for rationale; auto-gate path accepts empty string silently
- [ ] `qw query --name recent_champions` output includes `promotion_rationale` field
- [ ] Demo seed Cypher includes realistic `promotion_rationale` strings on all Champion MERGE
  blocks
- [ ] Existing Champion nodes without `promotion_rationale` are unaffected (field nullable;
  no migration required)

## Definition of Done
- [ ] `promotion_rationale` added to PROVENANCE_ENGINE.md Champion properties table
- [ ] `data_dictionary.yaml` updated
- [ ] `--rationale` flag implemented on `qw champion`; required for manual, optional for auto
- [ ] `recent_champions` preset returns `promotion_rationale` in output
- [ ] Demo seed has realistic rationale strings on all Champion nodes
- [ ] All tests pass (`ruff check .` and `mypy --strict .` clean)
- [ ] Story marked CLOSED
