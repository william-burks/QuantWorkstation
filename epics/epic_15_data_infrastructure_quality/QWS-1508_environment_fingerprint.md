# Story — Environment Fingerprint on Run

## ID
QWS-1508

## Status
PLANNED

## Type
code

## Blocked On
QWS-1507, QWS-1304

## Summary
Store `python_version`, `pkg_lock_hash`, and `random_seed` on every Run node so the reproduction environment is documented at ingest time.

## Problem
No record of what Python version or package set a trial ran under. Cannot detect when a package upgrade silently changes strategy behavior. Cannot reproduce a trial without knowing its exact environment.

## Goal
After `qw record --bundle`: `python_version`, `pkg_lock_hash`, `random_seed` written to Run node; old bundles ingest cleanly with `None`; `env_drift` preset identifies Runs with differing `pkg_lock_hash`.

## Design
- New Run properties must be `Optional[str] = None` — existing Run construction in tests must not break; backward-compatible with no `env` block in old bundles
- `pkg_lock_hash`: `hashlib.sha256(subprocess.run(['pip', 'freeze'], capture_output=True).stdout).hexdigest()` — if pip unavailable (conda env, restricted shell), fall back to hashing `pyproject.toml` contents only and log `WARNING "pip unavailable; pkg_lock_hash computed from pyproject.toml only"`
- `random_seed` is opt-in from `bundle.json` `env.random_seed` field; trial scripts that set a seed write it to bundle; trial scripts that don't are `None`
- Bundle flow: trial writes `env: {random_seed: <int_or_null>}` (or omits `env` block entirely); `qw record --bundle` fills in `python_version` + `pkg_lock_hash` at ingest time from current process; `random_seed` is merged from bundle if present
- `research/graph/cypher.py` `CSV_INGEST_QUERY` SET clause must be updated with null-safe properties for all three new Run fields
- Test isolation: mock `subprocess.run(['pip', 'freeze'], ...)` — do not actually run pip install in tests

## In Scope
- `research/graph/models.py` — add `python_version: Optional[str] = None`, `pkg_lock_hash: Optional[str] = None`, `random_seed: Optional[str] = None` to `Run` model
- `research/graph/cli.py` — update `_cmd_bundle()` to populate `python_version` + `pkg_lock_hash` from current process; merge `random_seed` from bundle if present
- `research/graph/cypher.py` — update `CSV_INGEST_QUERY` SET clause with null-safe properties for all three fields
- `research/graph/query_presets.py` — add `env_drift` preset

## Repo Touchpoints
- `research/graph/models.py` — three new Optional[str] properties on `Run`
- `research/graph/cli.py` — `_cmd_bundle()` populates env fingerprint at ingest time
- `research/graph/cypher.py` — `CSV_INGEST_QUERY` SET clause updated
- `research/graph/query_presets.py` — `env_drift` preset

## Acceptance Criteria
- [ ] `python_version`, `pkg_lock_hash`, `random_seed` written to Run node after `qw record --bundle`
- [ ] Old bundles (no `env` block) ingest cleanly with `None` for all three properties
- [ ] `pkg_lock_hash` is stable within same venv across multiple ingest calls (same process)
- [ ] `env_drift` preset returns Runs with differing `pkg_lock_hash`
- [ ] Unit test: mock `subprocess.run(['pip', 'freeze'])` returns known output → hash is deterministic; pip unavailable → WARNING logged, hash computed from pyproject.toml

## Definition of Done
- [ ] All ACs passing
- [ ] `make verify` passes (ruff, mypy, pytest)
- [ ] Story marked CLOSED

## Acceptance Test Plan

### AC1: env fields written to Run node
- type: integration
- cmd: `source .venv/bin/activate && pytest tests/integration/test_env_fingerprint.py -k "fields_written" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC2: old bundle ingests cleanly with None
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_env_fingerprint.py -k "old_bundle_none" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC3: pkg_lock_hash stable within process
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_env_fingerprint.py -k "hash_stable" -v 2>&1 | tail -5`
- expect_contains: "passed"

### AC4: env_drift preset
- type: cli
- cmd: `source .venv/bin/activate && qw query --name env_drift 2>&1 | head -5`
- expect_exit: 0

### AC5: mock pip → deterministic hash; pip unavailable → WARNING
- type: unit
- cmd: `source .venv/bin/activate && pytest tests/unit/test_env_fingerprint.py -k "mock_pip" -v 2>&1 | tail -5`
- expect_contains: "passed"
