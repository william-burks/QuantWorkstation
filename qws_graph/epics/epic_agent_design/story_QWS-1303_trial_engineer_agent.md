# Story 3 — Trial Engineer Agent

## ID
QWS-1303

## Status
BLOCKED

## Type
code

## Blocked On
QWS-1302 (navigator handoff contract), QWS-0907 (trial_metadata — bundle.json must include hypothesis_id)

## Summary
Extract ~200-line trial boilerplate to `trial_base.py`, then build `trial-engineer` agent that generates trial scripts from a hypothesis input contract, writes script + bundle template, and stops. Does not auto-run.

## Problem
Trial scripts are written from scratch each session with ~200 lines of boilerplate overlap (`_compute_atr`, `_prepare`, `_compute_metrics`, `_write_html`, argparse skeleton, bundle.json writing). Session 0901 produced 11 trial scripts manually. Each new strategy family requires re-implementing the same scaffolding.

## Goal
After this story:
1. `research/trials/trial_base.py` exists — shared scaffolding extracted from existing scripts; trials import from it
2. `trial-engineer` agent accepts: hypothesis_id, instrument, timeframe, trial_type, strategy_class, entry_logic (prose), exit_logic (prose), optional config_overrides
3. Agent generates: trial script at `research/trials/<asset>/<strategy>/NN_description.py` + bundle.json template in same dir
4. Agent STOPS after write — prints path + "Review, then run: `python -m research.trials.<module>`"
5. After explicit "run it": executes script, runs `qw record --bundle`, reports metrics in standard format

## Design
- Boilerplate extraction is AC-1 — trial-engineer agent cannot be built without it
- `trial_base.py` exports: `prepare_data()`, `compute_metrics()`, `write_html()`, `make_bundle()`
- Agent model: Sonnet (mechanical code generation, not reasoning-heavy)
- STOP gate is explicit in agent file: after write, print path and await instruction before executing
- Guard enforces: generated bundle.json must contain `hypothesis_id` field before run is permitted
- Trial NN = max existing NN + 1; guard blocks if numbering is wrong

## In Scope
- `research/trials/trial_base.py` — extracted boilerplate; existing trial scripts updated to import from it
- `.claude/agents/trial-engineer.md` — agent definition: input contract, output contract, STOP gate, tool list
- `.claude/scripts/agent-trial-guard.sh` — create or update if file exists
- Guardrail: bundle.json must include `hypothesis_id` before guard permits `qw record --bundle`

## Out of Scope
- Auto-running without explicit "run it" approval
- Backtest parameter optimization or sweep generation
- Multi-trial batches in one agent call
- Modifying existing trial scripts beyond boilerplate import refactor

## Repo Touchpoints
- `research/trials/trial_base.py` — new file
- `research/trials/<existing scripts>` — import updates only
- `.claude/agents/trial-engineer.md` — new file
- `.claude/scripts/agent-trial-guard.sh` — new or updated file

## Acceptance Criteria
- [ ] `research/trials/trial_base.py` exists and exports `prepare_data`, `compute_metrics`, `write_html`, `make_bundle`
- [ ] At least 3 existing trial scripts updated to import from `trial_base.py`; behavior unchanged (same output)
- [ ] `.claude/agents/trial-engineer.md` exists with input contract, output contract, and explicit STOP gate documented
- [ ] Agent generates valid trial script at correct path with correct NN (max+1)
- [ ] Agent generates bundle.json template in same dir as script
- [ ] Agent prints path and stop message after write; does not execute without explicit "run it"
- [ ] After "run it": executes script, runs `qw record --bundle`, reports Sharpe, max_dd, n_trades in single output block
- [ ] `agent-trial-guard.sh` blocks: writes to `execution/`, `data/collectors/`, `util/`, git operations
- [ ] `agent-trial-guard.sh` blocks `qw record --bundle` if bundle.json missing `hypothesis_id`
- [ ] `agent-trial-guard.sh` blocks trial script write if proposed NN ≠ max existing NN + 1
- [ ] Tool list in agent file: Read, Write (scoped to `research/trials/` and `research/results/` only), Bash (scoped to `python` execution and `qw record --bundle` only)

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green (where applicable)
- [ ] Story marked CLOSED
