# Story 12 — Strategy Class Taxonomy

## ID
QWS-1012

## Status
TESTING

## Type
schema

## Blocked On
None

## Summary
Add `strategy_class` free-form string property to Strategy nodes so strategies can be grouped by mechanism (e.g. `liquidity_sweep`, `momentum_breakout`) — enabling class-level champion coverage queries and portfolio construction across strategy types.

**Epic 10 blocker:** This story MUST be CLOSED before any Epic 10 collector story closes. Macro data strategies will create new Strategy nodes; without `strategy_class` present at write time, every new node requires retroactive backfill.

## Problem
Strategies accumulate across instruments and mechanisms with no higher-level grouping. `logic_type` (derived from filename stem) is inconsistent. No way to answer:
- "What strategy classes have champions?"
- "Which classes are over-represented vs. unexplored?"
- "How do I construct a portfolio across uncorrelated classes?"

## Goal
- `MATCH (s:Strategy) RETURN s.strategy_class, count(s)` returns meaningful buckets
- `qw query --name portfolio_by_class` groups champions and candidates by class
- `qw record --bundle` accepts `strategy_class` from `bundle.json`
- New strategies are classified at write time — no retroactive backfill needed for Epic 10+

## Schema Extension
| Element | Type | Properties | Notes |
|---|---|---|---|
| `Strategy` | Node | `strategy_class: string` | new nullable property; free-form lowercase underscore |

All additions must be registered in `qws_graph/docs/data_dictionary.yaml`.

## In Scope
- Add `strategy_class` nullable string to Strategy node (no enum — free-form)
- `bundle.json` manifest accepts `strategy_class` field alongside `strategy_id`, `hypothesis_id`
- `qw record --bundle` reads and writes `strategy_class` to node
- `portfolio_by_class` query preset: group champions + candidates by `strategy_class`
- `qw backfill --strategy-class` interactive CLI: for each Strategy node missing class, print title and prompt for value
- CLI tab-complete / suggestion: print existing distinct `strategy_class` values before prompting
- `data_dictionary.yaml` updated with property definition and starter taxonomy note

## Out of Scope
- Enum enforcement or validation — free-form only
- Migrating `logic_type` to `strategy_class` — separate story if needed
- Any changes to Epic 10 collector stories
- Portfolio construction logic — class grouping only

## Repo Touchpoints
<!-- MAX 5 FILES -->
- `qws_graph/docs/data_dictionary.yaml` — register `strategy_class` property
- `qws_graph/research/graph/store.py` — read `strategy_class` from bundle, write to Strategy node
- `qws_graph/research/graph/presets/portfolio_by_class.cypher` — new query preset
- `qws_graph/cli/backfill.py` — new `qw backfill --strategy-class` interactive command
- `qws_graph/tests/unit/test_strategy_class.py` — new

## Acceptance Criteria
- [x] `MATCH (s:Strategy {strategy_class: 'liquidity_sweep'}) RETURN s` returns nodes after backfill
- [x] `qw record --bundle bundle.json` with `strategy_class` field writes property to Strategy node
- [x] `qw query --name portfolio_by_class` executes without error and groups by class
- [x] `qw backfill --strategy-class` prompts for each unclassified strategy and writes value
- [x] Strategy node created without `strategy_class` does not error — property nullable
- [x] `data_dictionary.yaml` contains `strategy_class` entry with type, description, example values

## Definition of Done
- [x] data_dictionary.yaml updated
- [x] Tests green
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: strategy_class nullable — no error without property
- type: regression
- cmd: `source .venv/bin/activate && python3 -c "from qws_graph.research.graph.models import Strategy; s=Strategy(strategy_id='x',instrument='ES',timeframe='1h',direction='bear',logic_type='t'); assert s.strategy_class is None; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC2: data_dictionary.yaml contains strategy_class
- type: file_check
- cmd: `grep 'strategy_class:' qws_graph/docs/data_dictionary.yaml && grep 'liquidity_sweep' qws_graph/docs/data_dictionary.yaml`
- expect_contains: "strategy_class:"
- expect_exit: 0

### AC3: portfolio_by_class preset registered and callable without graph
- type: cli
- cmd: `source .venv/bin/activate && python3 -c "from qws_graph.research.graph.query_presets import PRESET_CATALOG; assert 'portfolio_by_class' in PRESET_CATALOG; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC4: qw backfill --strategy-class flag visible
- type: cli
- cmd: `source .venv/bin/activate && qw backfill --help`
- expect_contains: "--strategy-class"
- expect_exit: 0

### AC5: qw query --name portfolio_by_class recognized by preset system
- type: cli
- cmd: `source .venv/bin/activate && python3 -c "from qws_graph.research.graph.query_presets import resolve_preset; spec=resolve_preset('portfolio_by_class'); print(spec.name)"`
- expect_contains: "portfolio_by_class"
- expect_exit: 0

### AC6: bundle.json strategy_class read path exists in cli
- type: regression
- cmd: `source .venv/bin/activate && python3 -c "import inspect, qws_graph.research.graph.cli as c; src=inspect.getsource(c._cmd_bundle); assert 'strategy_class' in src; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0
