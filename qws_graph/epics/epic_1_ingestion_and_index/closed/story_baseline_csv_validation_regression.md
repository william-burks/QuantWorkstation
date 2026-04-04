# Story: Baseline CSV Validation Regression After Rollback

## Status
CLOSED

## Context
Phase 1/2 research runners currently generate baseline artifacts that fail graph ingest validation with:

`missing required columns: max_drawdown, profit_factor, sharpe, total_trades, win_rate`

This regressed after rollback. The ingestion contract for `baseline_csv` requires summary-level columns, while current baseline strategy outputs are trade-level rows.

## Problem Statement
`qw record --kind baseline_csv` must accept baseline outputs from:
- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`

Today these flows emit CSVs that do not satisfy the parser contract in `qws_graph/research/graph/parsers.py`.

## Goal
Restore baseline artifact compatibility with graph ingestion by ensuring baseline scripts write parser-compatible summary rows (not trade rows) for single-run baseline outputs.

## Scope
In scope:
- Baseline single-run CSV output shape for ES and NQ baseline scripts.
- Shared artifact helper for stable baseline schema generation.
- Unit tests for helper mapping and parser compatibility.

Out of scope:
- Strategy logic changes (entries/exits/metrics calculation).
- Grid search ranking logic.
- Neo4j schema changes.

## Acceptance Criteria
1. Running `research/run_es_nq_bear_sweep_1h_baseline.sh` produces:
   - `results/es_bear_sweep_1h_baseline.csv`
   - `results/nq_bear_sweep_1h_baseline.csv`
   with required columns:
   - `total_trades`
   - `win_rate`
   - `profit_factor`
   - `sharpe`
   - `max_drawdown`
2. Running `research/run_es_phase2.sh 1a` produces a parser-valid baseline CSV for `results/es_bear_sweep_1h_nypre.csv`.
3. `qw record --kind baseline_csv` no longer emits missing-column validation errors for those outputs.
4. Existing `grid_csv` behavior remains unchanged.
5. Unit tests pass for:
   - `tests/unit/test_strategy_artifacts.py`
   - `qws_graph/tests/unit/test_graph_parsers.py`

## Implementation Tasks
- [ ] Add baseline summary builder in `strategies/common/strategy_artifacts.py`:
  - map `sample_size -> total_trades`
  - map `avg_r_per_trade -> avg_r`
  - map `max_drawdown_r -> max_drawdown`
  - include config fields recognized by parser (`allowed_sessions`, `target_r`, `wick_mode`, `atr_mult_stop`, etc.)
- [ ] Export helper from `strategies/common/__init__.py`.
- [ ] Update single-run output path in:
  - `strategies/bear_es_sweep_1h_baseline.py`
  - `strategies/bear_nq_sweep_1h_baseline.py`
  to write one-row baseline summary CSV.
- [ ] Keep grid mode output unchanged.
- [ ] Add helper tests in `tests/unit/test_strategy_artifacts.py` for schema + mapping.
- [ ] Confirm parser tests still pass without widening aliases.

## Risks and Mitigations
- Risk: contract drift between strategy outputs and parser required columns.
  - Mitigation: lock helper schema in unit tests and validate via parser tests.
- Risk: accidental change to grid output format.
  - Mitigation: isolate changes to single-run baseline branch only.
- Risk: missing strategy metadata when parser infers identifiers.
  - Mitigation: emit explicit `instrument/timeframe/direction/logic_type` in baseline CSV.

## Verification Plan
Run:

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
pytest -q tests/unit/test_strategy_artifacts.py
cd /Users/will/ClaudeProjects/QuantWorkstation/qws_graph
pytest -q tests/unit/test_graph_parsers.py
```

End-to-end:

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/run_es_nq_bear_sweep_1h_baseline.sh
QW_GRAPH_ENABLED=false zsh research/run_es_phase2.sh 1a
```

Header spot-check:

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
head -n 1 results/es_bear_sweep_1h_baseline.csv
head -n 1 results/nq_bear_sweep_1h_baseline.csv
head -n 1 results/es_bear_sweep_1h_nypre.csv
```

Expected: required baseline columns present and no missing-column validation errors.

## Definition of Done
- Story tasks complete.
- Acceptance criteria met.
- Validation errors removed from baseline and phase2 runner flows.
- Tests pass and evidence logged in epic tracker/changelog.

