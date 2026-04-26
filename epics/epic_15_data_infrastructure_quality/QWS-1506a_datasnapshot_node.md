# Story — DataSnapshot Node + Hash

## ID
QWS-1506a

## Status
PLANNED

## Type
code

## Blocked On
None

## Summary
Define the `DataSnapshot` data structure, content-hashing mechanism, and `make_bundle()` extension that enables reproducibility tracking for trial bar data.

## Problem
ArcticDB append overwrites on reseed. Zero record of what data looked like at trial time. Cannot reproduce a backtest from 30 days ago. 50+ ML Runs generated without snapshot infrastructure cannot be reproduced after a reseed.

## Goal
`Store.snapshot_id()` returns a stable SHA-256 hash of bar slice content; `DataSnapshot` model defined; `make_bundle()` accepts `data_snapshots` parameter; Neo4j uniqueness constraint documented.

## Design
**Hash specification (locked):**
- Serialization: `hashlib.sha256(df.to_parquet()).hexdigest()` over the exact bar slice consumed by the trial
- Hash is purely content-based — NO timestamp in the hash input; same data must always produce same hash across concurrent ingests
- Cache: module-level dict `_snapshot_cache: dict[tuple[str, str, str, str], str]` keyed by `(lib, symbol, str(start), str(end))` in `data/store.py` — only useful within a single process; noted limitation

**Hash flow (trial → ingest):**
1. Trial script reads bars (e.g. `store.read_bars('futures', 'MES_1H', start=..., end=...)`)
2. Trial script writes `data_snapshots` block to `bundle.json` via updated `make_bundle()` — each entry: `{symbol, lib, timeframe, date_range_start, date_range_end}`; does NOT compute hash (trial script has no graph dependency)
3. `qw record --bundle` reads `data_snapshots` declarations, calls `Store.snapshot_id(lib, symbol, start, end)` per entry, computes hash; adds resolved hashes to bundle payload before graph write

**Neo4j constraint — one-time setup:**
`CREATE CONSTRAINT datasnapshot_content_hash IF NOT EXISTS FOR (n:DataSnapshot) REQUIRE n.content_hash IS UNIQUE`
Must run before Phase B goes live. Document as a one-time step in `research/graph/setup.py`.

## In Scope
- `data/store.py` — new `Store.snapshot_id(library, symbol, start, end) -> str`; new `Store.get_symbol_info(library, symbol)` if not already added by QWS-1501; module-level `_snapshot_cache` dict
- `research/graph/models.py` — new `DataSnapshot` dataclass with properties: `content_hash`, `symbol`, `lib`, `timeframe`, `date_range_start`, `date_range_end`, `snapshot_ts`, `row_count`
- `research/trials/trial_base.py` — `make_bundle()` gains optional `data_snapshots: list[dict] | None = None` parameter; writes `data_snapshots` block to `bundle.json`
- `docs/graph/data_dictionary.yaml` — add `DataSnapshot` node definition
- `research/graph/setup.py` — document Neo4j uniqueness constraint on `DataSnapshot.content_hash` as a one-time setup step

## Repo Touchpoints
- `data/store.py` — `Store.snapshot_id(library, symbol, start, end) -> str`; `_snapshot_cache` dict; `Store.get_symbol_info()` if not present
- `research/graph/models.py` — `DataSnapshot` dataclass
- `research/trials/trial_base.py` — `make_bundle()` gains `data_snapshots` parameter
- `docs/graph/data_dictionary.yaml` — `DataSnapshot` node definition
- `research/graph/setup.py` — uniqueness constraint documented

## Acceptance Criteria
- [ ] `Store.snapshot_id('futures', 'MES_1H', start, end)` returns a 64-char hex string
- [ ] Same bar data → same hash (stable across two calls within same process)
- [ ] Different bar data (post-reseed) → different hash
- [ ] `Store.get_symbol_info()` returns SymbolDescription without reading full bar data (verified: no `read_bars()` call in implementation)
- [ ] `make_bundle(data_snapshots=[...])` writes `data_snapshots` array to `bundle.json`
- [ ] `docs/graph/data_dictionary.yaml` contains `DataSnapshot` node with all properties
- [ ] Neo4j uniqueness constraint on `DataSnapshot.content_hash` documented in `research/graph/setup.py` as a setup step
- [ ] Performance: `Store.snapshot_id()` for a 2yr 1H series completes in <5s (verified via `time`)

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: snapshot_id returns 64-char hex
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_store_snapshot.py -k "returns_64_char_hex" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC2: same data → same hash
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_store_snapshot.py -k "same_data_same_hash" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: different data → different hash
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_store_snapshot.py -k "different_data_different_hash" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: get_symbol_info no read_bars call
- type: file_check
- cmd: `grep -A 10 "def get_symbol_info" data/store.py`
- expect: implementation uses `get_description`, not `read_bars`

### AC5: make_bundle writes data_snapshots to bundle.json
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_trial_base.py -k "data_snapshots_in_bundle" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC6: data_dictionary.yaml updated
- type: file_check
- cmd: `grep -n "DataSnapshot" docs/graph/data_dictionary.yaml`
- expect_contains: "DataSnapshot"
- expect_exit: 0

### AC7: constraint in setup.py
- type: file_check
- cmd: `grep -n "datasnapshot_content_hash\|DataSnapshot" research/graph/setup.py`
- expect_contains: "DataSnapshot"
- expect_exit: 0

### AC8: performance <5s
- type: cli
- cmd: `time source .venv/bin/activate && python -c "from data.store import get_store; s=get_store(); s.snapshot_id('futures','MES_1H','2023-01-01','2025-01-01')" 2>&1 | tail -3`
- expect: elapsed < 5s
