# Story 2 — OpenAI Curation Switch

## ID
QWS-0703

## Status
CLOSED

## Blocked On
None

## Summary
Replace `LlamaAnalyst` (local llama-stack server) with `OpenAIAnalyst` (OpenAI API). Flip
AI curation from opt-in (`--analyze`) to opt-out (`--no-analyze`). Removes the local server
dependency; curation runs by default for all `grid_csv` ingests.

## Problem
Current AI curation requires a running local Llama 4 Scout server (`llama stack run local
--port 5001`). Setup is high-friction, fragile, and blocks curation from being the default.

The `--analyze` flag means curation is off unless explicitly requested. Most ingests skip
curation entirely.

Switching to OpenAI API eliminates the local server dependency and makes `OPENAI_API_KEY`
(already expected to exist in env) the only requirement.

## Goal

```zsh
# Default (curation on — new behavior)
qw record --file results/grid.csv --kind grid_csv

# Disable curation explicitly
qw record --file results/grid.csv --kind grid_csv --no-analyze

# Old --analyze flag: removed (curation is now default)
```

## Schema
No new nodes or edges. `Run.curator_note` property already exists (QWS-0211C CLOSED). No
schema changes.

## In Scope
- `research/graph/analyst.py` — replace `LlamaAnalyst` class with `OpenAIAnalyst`; rename
  `LlamaUnavailableError` to `AnalystUnavailableError`; update `from_env()` to read
  `OPENAI_API_KEY` and `QW_AI_ANALYST_MODEL` (default: `gpt-4o-mini`)
- `research/graph/cli.py` — remove `--analyze` flag; add `--no-analyze` flag; flip
  orchestration logic in `cmd_record` so semantic tier is default, math-only is the fallback
  when `--no-analyze` passed or `OPENAI_API_KEY` unset
- `tests/unit/test_analyst.py` — update existing tests: replace mock llama client with mock
  openai client; class names; error type
- Remove `llama-stack-client` from `pyproject.toml` dependencies; add `openai` if not already
  present
- Update `docs/graph_v1_contract.md` — update analyst section to reflect OpenAI and new default

## Out of Scope
- Prompt redesign (same compact CSV format, same `AnnotationResult` dataclass)
- Changing `curator_note` storage or query surface
- Adding new query presets
- Changing the math tier logic in `curator.py`

## Repo Touchpoints
- `research/graph/analyst.py`
- `research/graph/cli.py`
- `tests/unit/test_analyst.py`
- `pyproject.toml`
- `docs/graph_v1_contract.md`

## Acceptance Criteria
- [x] `qw record --kind grid_csv` (no flags) invokes AI curation via OpenAI API when
  `OPENAI_API_KEY` is set
- [x] `qw record --kind grid_csv --no-analyze` skips AI curation and runs math-tier only
- [x] `qw record --kind grid_csv` when `OPENAI_API_KEY` is unset falls back to math-tier
  with `WARNING: AI analyst unavailable — falling back to math tier` on stderr
- [x] `OpenAIAnalyst.from_env()` reads `OPENAI_API_KEY` from environment; raises
  `AnalystUnavailableError` if unset
- [x] `QW_AI_ANALYST_MODEL` env var controls the OpenAI model; defaults to `gpt-4o-mini`
  when unset
- [x] `--analyze` flag no longer accepted by `qw record` (removed)
- [x] Existing unit tests in `test_analyst.py` pass with mock OpenAI client replacing mock
  Llama client
- [x] `llama-stack-client` is removed from `pyproject.toml` dependencies

## Acceptance Test Plan

### AC1: Default invokes OpenAI curation when key set
- type: cli
- cmd: `source .venv/bin/activate && python -c "from research.graph.analyst import OpenAIAnalyst, AnalystUnavailableError; import os; os.environ['OPENAI_API_KEY']='sk-test'; a = OpenAIAnalyst.from_env(); print(a._model_id)"`
- expect_contains: "gpt-4o-mini"
- expect_exit: 0

### AC2: --no-analyze skips curation (unit test coverage)
- type: cli
- cmd: `source .venv/bin/activate && pytest qws_graph/tests/unit/test_analyst.py -v 2>&1 | tail -5`
- expect_contains: "passed"
- expect_exit: 0

### AC3: Missing OPENAI_API_KEY raises AnalystUnavailableError
- type: cli
- cmd: `source .venv/bin/activate && python -c "from research.graph.analyst import OpenAIAnalyst, AnalystUnavailableError; import os; [os.environ.pop(k, None) for k in ['OPENAI_API_KEY']]; OpenAIAnalyst.from_env()" 2>&1`
- expect_contains: "OPENAI_API_KEY is not set"
- expect_exit: 1

### AC4: QW_AI_ANALYST_MODEL controls model
- type: cli
- cmd: `source .venv/bin/activate && python -c "from research.graph.analyst import OpenAIAnalyst; import os; os.environ['OPENAI_API_KEY']='sk-x'; os.environ['QW_AI_ANALYST_MODEL']='gpt-4o'; a=OpenAIAnalyst.from_env(); print(a._model_id)"`
- expect_contains: "gpt-4o"
- expect_exit: 0

### AC5: --analyze flag rejected
- type: cli
- cmd: `source .venv/bin/activate && python -m research.graph.cli record --file /dev/null --kind grid_csv --analyze 2>&1`
- expect_contains: "error: unrecognized arguments"
- expect_exit: 2

### AC6: llama-stack-client absent from pyproject.toml
- type: file_check
- cmd: `grep 'llama-stack-client' qws_graph/pyproject.toml`
- expect_contains: ""
- expect_exit: 1

### AC7: Unit tests pass
- type: cli
- cmd: `source .venv/bin/activate && pytest qws_graph/tests/unit/test_analyst.py -v 2>&1 | grep -E 'passed|failed|error'`
- expect_contains: "passed"
- expect_exit: 0

## Definition of Done
- [x] `OpenAIAnalyst` implemented; `LlamaAnalyst` and `LlamaUnavailableError` removed
- [x] CLI default flipped: curation on by default, `--no-analyze` disables
- [x] All tests pass (`ruff check .` and `mypy --strict .` clean)
- [x] `docs/graph_v1_contract.md` updated
- [x] All affected README files updated
- [x] PROVENANCE_ENGINE.md updated if new nodes/edges/properties introduced (none expected)
- [x] Story marked CLOSED
