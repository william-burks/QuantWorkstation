# Story 1 — Hypothesis & Research Journaling

## ID
QWS-0601

## Status
draft

## Summary
Introduce `:Hypothesis` nodes that link qualitative research hypotheses to one or more
`:Run` nodes. Turns the graph into a research journal where "why I ran this" is
permanently connected to "what the results showed." Directly addresses context drift.

## Problem
Research context lives in the researcher's head, in Slack messages, or in scattered
markdown notes. Six months after a test run:
- Why was this parameter sweep done? Unknown.
- Which hypothesis did this golden run confirm or refute? Unknown.
- Are runs A, B, and C part of the same research thread? Unknown.

`curator_note` on Run nodes helps for single-run annotations but cannot link a
hypothesis to multiple runs or track whether the hypothesis was confirmed.

## Goal
```zsh
# Record a new hypothesis
qw record --hypothesis "Tuesday London Open has a specific liquidity trap in CL bear"

# Link runs to it (by run_id)
qw record --hypothesis <hypothesis_id> --link-run <run_id>
qw record --hypothesis <hypothesis_id> --link-run <run_id> --evidence supports
qw record --hypothesis <hypothesis_id> --link-run <run_id> --evidence refutes

# Query
qw query --name list_hypotheses
qw query --name hypothesis_evidence --param hypothesis_id=<id>
```

## Schema

### `:Hypothesis` node
```
hypothesis_id: str          # hash12(title, created_at_iso)
title: str                  # short description (≤ 200 chars)
status: str                 # open | confirmed | refuted | abandoned
created_at: datetime
updated_at: datetime
```

### `HAS_EVIDENCE` edge: `(Hypothesis)-[:HAS_EVIDENCE]->(Run)`
```
evidence_type: str          # supports | refutes | inconclusive (default: inconclusive)
note: str | null            # optional free-text annotation on this specific link
linked_at: datetime
```

## CLI surface
- `qw record --hypothesis "<title>"` — creates a new Hypothesis node, prints
  `hypothesis_id`.
- `qw record --hypothesis <id> --link-run <run_id>` — adds a `HAS_EVIDENCE` edge.
  `--evidence supports|refutes|inconclusive` (default: `inconclusive`).
  `--note "<text>"` optional annotation on the edge.
- `qw record --hypothesis <id> --status confirmed` — updates `status` on the node.

## Query presets
- `list_hypotheses` — all Hypothesis nodes, ordered by `created_at` DESC. Columns:
  `hypothesis_id`, `title`, `status`, `evidence_count`, `created_at`.
- `hypothesis_evidence --param hypothesis_id=<id>` — all Run nodes linked to a
  hypothesis with their `evidence_type`, `sharpe`, `total_trades`, `regime` (if set).

## In Scope
- `:Hypothesis` node and `HAS_EVIDENCE` edge in `store.py`
- Three new CLI modes on `qw record`
- Two new query presets
- `data_dictionary.yaml` and `graph_v1_contract.md` updated
- Unit tests for store methods and CLI parsing

## Out of Scope
- AI-generated hypotheses
- Hypothesis versioning or branching
- Linking hypotheses to Champion or Config nodes (Run-only in V1)

## Acceptance Criteria
- [ ] `qw record --hypothesis "Test title"` creates a Hypothesis node and prints its ID.
- [ ] `qw record --hypothesis <id> --link-run <run_id> --evidence supports` creates
  a `HAS_EVIDENCE` edge with `evidence_type = "supports"`.
- [ ] `qw query --name list_hypotheses` returns all hypotheses with evidence counts.
- [ ] `qw query --name hypothesis_evidence --param hypothesis_id=<id>` returns linked runs.
- [ ] `qw record --hypothesis <id> --status confirmed` updates `status` on the node.
- [ ] Linking a non-existent `run_id` returns a clear error.

## Definition of Done
- [ ] Node type, edges, CLI modes, query presets implemented and tested.
- [ ] Docs updated.
- [ ] Story marked CLOSED.
