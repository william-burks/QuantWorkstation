# Story — Strategy Input Contract

## ID
QWS-1507

## Status
PLANNED

## Type
code

## Blocked On
QWS-1304

## Summary
Add `InputContract` to `BaseStrategy`, `qw validate --strategy` CLI subparser, and `InputSpec`/`REQUIRES` graph integration so each strategy declares its required ArcticDB symbols.

## Problem
Strategies can silently pull any data. No declared dependency surface. Cannot answer "what strategies will break if we drop MNQ 1H?". Epic 12 feature engineering (QWS-1203) makes this worse — ML strategies consuming computed features with no declared inputs.

## Goal
`InputContract` declared on strategies; `qw validate --strategy` enforces at trial time; `REQUIRES` edges written to graph at bundle ingest; `PROVENANCE_ENGINE.md` documents the new nodes/edges.

## Design
**BaseStrategy extension:**
```python
from typing import ClassVar, NamedTuple

class InputContract(NamedTuple):
    symbol: str
    lib: str
    timeframe: str
    min_bars: int
    optional: bool = False

class BaseStrategy(ABC):
    ...
    input_contracts: ClassVar[list[InputContract]] = []
```
Existing strategies inherit the empty list and pass `qw validate` silently.

**qw validate --strategy:**
New argparse subparser in `research/graph/cli.py`. Implementation requires:
1. Add `validate` subparser to the CLI argument parser
2. Dynamic strategy import: import module named in `strategies/<name>.py`, find the `BaseStrategy` subclass
3. Add `from data.store import get_store` import to `research/graph/cli.py` (new cross-module dep)
4. For each `InputContract`: call `store.has_symbol(lib, symbol)` and `store.get_symbol_info(lib, symbol)` to verify min_bars

**REQUIRES edge trigger:**
`REQUIRES` edge written during `qw record --bundle` when `input_contracts` data present in `bundle.json`. Flow:
1. Trial script writes `input_contracts` block to `bundle.json` (serialized from strategy class's `input_contracts` list)
2. `_cmd_bundle()` extracts `input_contracts` and calls new graph method to write `InputSpec` nodes + `REQUIRES` edges

**InputSpec node:**
Separate node (not property set on Strategy). Needs uniqueness constraint on composite key `(symbol, lib, timeframe)`. MERGE semantics: if same InputSpec already exists, just add the REQUIRES edge.

**trial-engineer agent update:**
Step 0b added: "Before Writing Any Trial": run `qw validate --strategy <name>`; BLOCKED output and halt on non-zero exit.

## In Scope
- `strategies/base.py` — add `InputContract` NamedTuple; add `input_contracts: ClassVar[list[InputContract]] = []` to `BaseStrategy`
- `research/graph/cli.py` — add `validate` subparser; add `from data.store import get_store`; implement `_cmd_validate_strategy()`
- `research/graph/cypher.py` — add `InputSpec` node + `REQUIRES` edge Cypher
- `research/graph/store.py` — add `GraphStore.write_input_contracts(run_id, input_contracts)`
- `research/trials/trial_base.py` — `make_bundle()` gains `input_contracts` parameter; written to `bundle.json`
- `docs/PROVENANCE_ENGINE.md` — add InputSpec node + REQUIRES edge sections
- `.claude/agents/trial-engineer.md` — add Step 0b: run `qw validate --strategy <name>` before writing any trial; BLOCKED on non-zero

## Repo Touchpoints
- `strategies/base.py` — `InputContract` NamedTuple; `input_contracts` class variable on `BaseStrategy`
- `research/graph/cli.py` — `validate` subparser; `from data.store import get_store`; `_cmd_validate_strategy()`; `_cmd_bundle()` updated for `input_contracts`
- `research/graph/cypher.py` — InputSpec node Cypher; REQUIRES edge Cypher
- `research/graph/store.py` — `GraphStore.write_input_contracts()`
- `research/trials/trial_base.py` — `make_bundle()` gains `input_contracts` parameter
- `docs/PROVENANCE_ENGINE.md` — InputSpec node + REQUIRES edge sections
- `.claude/agents/trial-engineer.md` — Step 0b

## Acceptance Criteria
- [ ] `InputContract` importable from `strategies/base.py`
- [ ] `qw validate --strategy <name>` exits non-zero if declared symbol not found in ArcticDB or has fewer bars than `min_bars`
- [ ] `qw validate --strategy <name>` exits 0 for strategies with empty `input_contracts` (no declared inputs → no checks → passes)
- [ ] `REQUIRES` edge written to graph after `qw record --bundle` for bundles with `input_contracts` block
- [ ] `InputSpec` node has uniqueness constraint on `(symbol, lib, timeframe)`
- [ ] trial-engineer agent has Step 0b; BLOCKED on validate failure
- [ ] `PROVENANCE_ENGINE.md` InputSpec node and REQUIRES edge sections complete
- [ ] Test: strategy declaring `{symbol: 'FAKE_1H', lib: 'futures', min_bars: 1000}` → `qw validate` exits non-zero

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: InputContract importable
- type: cli
- cmd: `source .venv/bin/activate && python -c "from strategies.base import InputContract; print('ok')"`
- expect_contains: "ok"

### AC2: validate exits non-zero for missing symbol
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_qw_validate.py -k "missing_symbol_nonzero" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: validate exits 0 for empty input_contracts
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_qw_validate.py -k "empty_contracts_passes" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: REQUIRES edge written at bundle ingest
- type: integration
- cmd: `source .venv/bin/activate && pytest tests/integration/test_requires_edge.py -k "edge_written" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC5: InputSpec uniqueness constraint
- type: file_check
- cmd: `grep -n "InputSpec\|symbol.*lib.*timeframe" research/graph/setup.py`
- expect_contains: "InputSpec"
- expect_exit: 0

### AC6: trial-engineer Step 0b
- type: file_check
- cmd: `grep -n "Step 0b\|validate.*strategy" .claude/agents/trial-engineer.md`
- expect_contains: "validate"
- expect_exit: 0

### AC7: PROVENANCE_ENGINE.md updated
- type: file_check
- cmd: `grep -n "InputSpec\|REQUIRES" docs/PROVENANCE_ENGINE.md`
- expect_contains: "InputSpec"
- expect_contains: "REQUIRES"
- expect_exit: 0

### AC8: fake symbol → non-zero exit
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_qw_validate.py -k "fake_symbol" -v 2>&1 | tail -5`
- expect_contains: "passed"
