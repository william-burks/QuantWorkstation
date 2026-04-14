# Story 3 — Trial Engineer Agent

## ID
QWS-1303

## Status
READY

## Type
code

## Blocked On
~~QWS-1302~~ (navigator handoff contract CLOSED), ~~QWS-HF-001~~ (hypothesis_id in bundle.json)

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
- STOP gate is explicit in agent file: after write, print path and await instruction before executing. STOP gate is instruction-only — agent prints the generated script path and stops; no guard enforcement. Guard is scoped to blocking destructive qw commands only.
- Guard enforces: generated bundle.json must contain `hypothesis_id` field before run is permitted
- Trial NN = max existing NN + 1; guard blocks if numbering is wrong

## In Scope
- `research/trials/trial_base.py` — extracted boilerplate; existing trial scripts updated to import from it
- `.claude/agents/trial-engineer.md` — update existing agent file: input contract, output contract, STOP gate, tool list
- `.claude/scripts/agent-trial-guard.sh` — update existing file
- Guardrail: bundle.json must include `hypothesis_id` before guard permits `qw record --bundle`

## Out of Scope
- Auto-running without explicit "run it" approval
- Backtest parameter optimization or sweep generation
- Multi-trial batches in one agent call
- Modifying existing trial scripts beyond boilerplate import refactor

## Repo Touchpoints
- `research/trials/trial_base.py` — new file
- `research/trials/<existing scripts>` — import updates only
- `.claude/agents/trial-engineer.md` — update existing file
- `.claude/scripts/agent-trial-guard.sh` — update existing file

## Acceptance Criteria
- [x] `research/trials/trial_base.py` exists and exports `prepare_data`, `compute_metrics`, `write_html`, `make_bundle`
- [x] At least 3 existing trial scripts updated to import from `trial_base.py`; behavior unchanged (same output)
- [x] `.claude/agents/trial-engineer.md` updated with input contract, output contract, and explicit STOP gate documented
- [x] Agent generates valid trial script at correct path with correct NN (max+1)
- [x] Agent generates bundle.json template in same dir as script
- [x] Agent prints path and stop message after write; does not execute without explicit "run it"
- [x] After "run it": executes script, runs `qw record --bundle`, reports Sharpe, max_dd, n_trades in single output block
- [x] `agent-trial-guard.sh` blocks: writes to `execution/`, `data/collectors/`, `util/`, git operations
- [x] `agent-trial-guard.sh` blocks `qw record --bundle` if bundle.json missing `hypothesis_id`
- [x] `agent-trial-guard.sh` blocks trial script write if proposed NN ≠ max existing NN + 1
- [x] Guard blocks execution if generated bundle.json is missing `hypothesis_id` field
- [x] Guard blocks execution if trial script filename does not match `NN_description.py` pattern
- [x] Tool list in agent file: Read, Write (scoped to `research/trials/` and `research/results/` only), Bash (scoped to `python` execution and `qw record --bundle` only)

## Definition of Done
- [x] All ACs passing
- [x] Tests green (where applicable)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: trial_base.py exports required symbols
- type: file_check
- cmd: `python -c "from research.trials.trial_base import prepare_data, compute_metrics, write_html, make_bundle, write_bundle; print('OK')"`
- expect_contains: "OK"
- expect_exit: 0

### AC2: 3 trial scripts import from trial_base
- type: file_check
- cmd: `grep -l "from research.trials.trial_base import" research/trials/crypto/btc_donchian/01_baseline.py research/trials/futures/liquidity_sweep/04_atr_filtered_baseline.py research/trials/futures/liquidity_sweep/05_5m_stop_stacked_filters.py | wc -l`
- expect_contains: "3"
- expect_exit: 0

### AC3: trial-engineer.md has input contract, output contract, STOP gate
- type: file_check
- cmd: `grep -c "Input Contract\|Output Contract\|STOP Gate" .claude/agents/trial-engineer.md`
- expect_contains: "3"
- expect_exit: 0

### AC6: guard blocks execution/ writes
- type: cli
- cmd: `echo '{"tool_name":"Write","tool_input":{"file_path":"execution/oms.py","content":"x"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 2

### AC7: guard blocks data/collectors/ writes
- type: cli
- cmd: `echo '{"tool_name":"Write","tool_input":{"file_path":"data/collectors/foo.py","content":"x"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 2

### AC8: guard blocks util/ writes
- type: cli
- cmd: `echo '{"tool_name":"Write","tool_input":{"file_path":"util/deleteData.py","content":"x"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 2

### AC9: guard blocks git commit
- type: cli
- cmd: `echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 2

### AC10: guard blocks qw record --bundle with missing hypothesis_id
- type: cli
- cmd: `TMPDIR=$(mktemp -d) && echo '{}' > $TMPDIR/bundle.json && echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"qw record --bundle $TMPDIR\"}}" | .claude/scripts/agent-trial-guard.sh; rm -rf $TMPDIR`
- expect_exit: 2

### AC11: guard allows qw record --bundle with valid hypothesis_id
- type: cli
- cmd: `TMPDIR=$(mktemp -d) && echo '{"hypothesis_id":"abc123def456"}' > $TMPDIR/bundle.json && echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"qw record --bundle $TMPDIR\"}}" | .claude/scripts/agent-trial-guard.sh; rm -rf $TMPDIR`
- expect_exit: 0

### AC12: guard blocks invalid trial filename
- type: cli
- cmd: `echo '{"tool_name":"Write","tool_input":{"file_path":"research/trials/crypto/btc_donchian/MyTrial.py","content":"x"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 2

### AC13: guard allows valid trial filename
- type: cli
- cmd: `echo '{"tool_name":"Write","tool_input":{"file_path":"research/trials/crypto/btc_donchian/05_new_trial.py","content":"x"}}' | .claude/scripts/agent-trial-guard.sh`
- expect_exit: 0
