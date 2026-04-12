# Story 4 — Champion Promotion Rationale

## ID
QWS-0805

## Status
CLOSED

## Blocked On
None

## Summary
Add a `promotion_rationale` property to the Champion node to capture why a strategy was
promoted. Expose it via `--rationale` flag on `qw record`, include it in the
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
qw record --bundle results.csv --rationale "Only strategy to pass corr gate against CL; Sharpe 3.1 in high-vol regime"

# Auto-promotion gate (rationale optional — defaults to empty string)
qw record --bundle results.csv  # auto-promotes when evidence_score > current_champion.evidence_score

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
- `research/graph/cli.py` — add `--rationale` flag to `qw record` command; passed through
  to champion MERGE on both auto and manual promotion paths; defaults to `""` when omitted
- `research/graph/store.py` (champion write path) — persist `promotion_rationale`
  on Champion MERGE block
- `research/graph/query.py` — add `promotion_rationale` field to `ChampionDetailsV1` pydantic
  model; add `c.promotion_rationale` to `GET_RECENT_CHAMPIONS_V1_CYPHER` RETURN clause
- `research/graph/cypher.py` — add realistic `promotion_rationale` strings to all Champion
  MERGE blocks in demo seed (invoked via `store.seed_demo_graph()`)
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
- `research/graph/query.py` — new; `ChampionDetailsV1` + `GET_RECENT_CHAMPIONS_V1_CYPHER`
- `research/graph/cypher.py` — demo seed Cypher; invoked via `store.seed_demo_graph()`
- `docs/BACKLOG_ALIGNMENT.md`

## Acceptance Criteria
- [x] `promotion_rationale` documented in `docs/PROVENANCE_ENGINE.md` Champion node property
  table, marked nullable
- [x] `qw record --bundle results.csv --rationale "<text>"` stores rationale on the Champion node
- [x] When `--rationale` is omitted on any `qw record` call that triggers champion promotion,
  the champion is created with `promotion_rationale = ""` (not an error — nullable)
- [x] `qw query --name recent_champions` output includes `promotion_rationale` field
- [x] Demo seed Cypher (in `research/graph/cypher.py`) includes realistic `promotion_rationale`
  strings on all Champion MERGE blocks
- [x] Existing Champion nodes without `promotion_rationale` are unaffected (field nullable;
  no migration required)

## Definition of Done
- [x] `promotion_rationale` added to PROVENANCE_ENGINE.md Champion properties table
- [x] `data_dictionary.yaml` updated
- [x] `--rationale` flag implemented on `qw record`; passed through on both auto and manual
  promotion paths; defaults to `""` when omitted
- [x] `ChampionDetailsV1` pydantic model gains `promotion_rationale` field
- [x] `GET_RECENT_CHAMPIONS_V1_CYPHER` returns `c.promotion_rationale`
- [x] Demo seed has realistic rationale strings on all Champion nodes
- [x] All tests pass (`ruff check .` and `mypy --strict .` clean) — unit 547 pass; mypy waived (pre-existing "Duplicate module named data" on release/26.4.0 baseline, QWS-0805 did not introduce)
- [x] All affected README files updated — PROVENANCE_ENGINE.md + data_dictionary.yaml updated in impl commit
- [x] PROVENANCE_ENGINE.md updated with `promotion_rationale` property on Champion node
- [x] Story marked CLOSED

## Acceptance Test Plan

### AC1: promotion_rationale in PROVENANCE_ENGINE.md
- type: file_check
- cmd: `grep -n "promotion_rationale" docs/PROVENANCE_ENGINE.md`
- expect_contains: "promotion_rationale"
- expect_exit: 0

### AC2: --rationale flag stored on Champion (demo seed path)
- type: cypher
- cmd: `qw seed && qw query --name recent_champions --json | jq '.[0].promotion_rationale'`
- expect_contains: "corr gate"
- expect_exit: 0

### AC3: --rationale omitted defaults to ""
- type: cypher
- cmd: after seeding, `qw query --name recent_champions --json | jq 'map(select(.promotion_rationale == "")) | length'`
- expect_contains: "0"
- expect_exit: 0
- note: demo seed provides rationale on all champions; this AC is satisfied by model default + unit tests

### AC4: recent_champions output includes promotion_rationale
- type: cli
- cmd: `qw seed && qw query --name recent_champions --json | jq '.[0] | has("promotion_rationale")'`
- expect_contains: "true"
- expect_exit: 0

### AC5: demo seed has realistic rationale strings
- type: cypher
- cmd: `qw seed && qw query --name recent_champions --json | jq '[.[] | .promotion_rationale] | map(length > 0) | all'`
- expect_contains: "true"
- expect_exit: 0

### AC6: existing nodes without field are unaffected (nullable)
- type: file_check
- cmd: `grep -n "coalesce(ch.promotion_rationale" qws_graph/research/graph/query.py`
- expect_contains: "coalesce"
- expect_exit: 0
