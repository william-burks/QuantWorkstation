# Story 5 — ResearchTarget Config Node

## ID
QWS-0408

## Status
READY

## Blocked On
None

## Summary
Introduce a singleton `ResearchTarget` node in the graph that stores the quantitative
promotion targets (Sharpe thresholds, frequency floor, holding limit, etc.). Makes
research constraints graph-queryable without requiring code edits.

## Problem
Research targets are currently hardcoded in `standards.py`. Two problems result:

1. An LLM with MCP access has no way to query "what are the current promotion targets?"
   without reading source files. It must be told out-of-band or infer from context.

2. Adjusting a target (e.g., raising the institutional Sharpe threshold from 3.5 to 4.0)
   requires a code change, PR, and re-ingest — rather than a single CLI command that
   updates the graph node.

MANIFESTO.md explicitly designates `ResearchTarget` as a target-state node. The promotion
gate logic in `standards.py` remains the authority for enforcement; this story makes the
values queryable and configurable without code changes.

## Goal
```zsh
# Seed / update the ResearchTarget node with defaults
qw seed --targets

# Read current targets
qw query --name research_targets

# Override one target
qw seed --targets --set sharpe_professional=2.5
```

The `research_targets` query preset returns all target properties in a single-row table
that any MCP client can read to understand current promotion criteria.

## Schema

### `:ResearchTarget` node (singleton — one node per graph)
| Property | Type | Default | Description |
|---|---|---|---|
| `sharpe_professional` | float | 2.0 | Minimum Sharpe for Professional tier |
| `sharpe_institutional` | float | 3.5 | Minimum Sharpe for Institutional tier |
| `max_holding_hours` | int | 4 | Maximum holding period in hours |
| `min_trades` | int | 30 | Absolute trade count floor |
| `min_active_window_frequency` | float | 0.06 | Minimum trades/day over active window |
| `profit_factor_min` | float | 1.3 | Minimum profit factor |
| `calmar_min` | float | 1.5 | Minimum Calmar ratio |
| `max_drawdown_floor` | float | -0.20 | Worst acceptable peak-to-trough (e.g. -0.20 = -20%) |
| `correlation_gate` | float | 0.30 | Maximum correlation to active Champions |
| `updated_at` | datetime | seeded datetime | Timestamp of last update |

Implemented as an idempotent MERGE on a fixed `target_id = "singleton"` property.

## In Scope
- `qws_graph/research/graph/store.py` — `ensure_research_target(overrides)` method: MERGE on
  singleton key, set defaults, apply any `--set` overrides
- `qws_graph/research/graph/cli.py` — `qw seed --targets` subcommand with optional
  `--set <key>=<value>` repeatable flag
- `qws_graph/research/graph/query_presets.py` — `research_targets` preset returning
  all properties of the singleton node
- `qws_graph/docs/data_dictionary.yaml` — document `:ResearchTarget` node and all properties
- `qws_graph/docs/graph_v1_contract.md` — add ResearchTarget to schema section
- Unit tests: seed creates node; re-seed is idempotent; `--set` overrides apply

## Out of Scope
- Making `standards.py` read from the graph at runtime (that is a separate coupling story)
- Per-strategy or per-instrument target overrides (global singleton only)
- Automatic re-seeding on `qw record` startup

## Repo Touchpoints
- `qws_graph/research/graph/store.py`
- `qws_graph/research/graph/cli.py`
- `qws_graph/research/graph/query_presets.py`
- `qws_graph/docs/data_dictionary.yaml`
- `qws_graph/docs/graph_v1_contract.md`
- `qws_graph/tests/unit/test_store_research_target.py` — new

## Acceptance Criteria
- [ ] `qw seed --targets` exits `0` and creates a `ResearchTarget` node with all default values.
- [ ] Running `qw seed --targets` a second time is idempotent — node properties are unchanged.
- [ ] `qw seed --targets --set sharpe_professional=2.5` updates `sharpe_professional` to `2.5`
  without modifying other properties.
- [ ] `qw seed --targets --set unknown_key=1.0` exits non-zero with a clear error.
- [ ] `qw query --name research_targets` returns a single row with all properties.
- [ ] `updated_at` is refreshed on every `qw seed --targets` call.
- [ ] Unit tests cover: first-time seed, idempotent re-seed, `--set` override, unknown key error.

## Definition of Done
- [ ] `ensure_research_target()` store method implemented and unit tested.
- [ ] `qw seed --targets` CLI subcommand wired up.
- [ ] `research_targets` query preset returns correct output.
- [ ] `data_dictionary.yaml` and `graph_v1_contract.md` updated.
- [ ] Story marked CLOSED.
- [ ] `docs/MANIFESTO.md` — ResearchTarget description updated from "target state — not yet implemented" to current state.
- [ ] `qws_graph/docs/qws_graph_runbook.md` — `qw seed --targets` added to Day-1 Operations section.
- [ ] `docs/PROVENANCE_ENGINE.md` — `ResearchTarget` node moved from `[TARGET]` to `[CURRENT]` node table.