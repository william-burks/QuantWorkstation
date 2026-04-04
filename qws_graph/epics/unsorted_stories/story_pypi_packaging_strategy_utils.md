# Story: Package Shared Strategy Utilities for PyPI

## Status
ready

## Problem
Shared strategy helper code now exists in-repo, but it is not packaged for external reuse. This blocks clean reuse across repositories and prevents versioned distribution via PyPI.

## Goal
Create a publishable Python package for shared strategy utilities with a stable API, tests, and release workflow.

## Deliverable
- Package scaffold for strategy utilities using `src/` layout
- Public API for shared helpers currently in `strategies/common/strategy_artifacts.py`
- Tests validating package behavior
- Packaging metadata and build configuration
- Initial publish runbook for TestPyPI and PyPI

## In Scope
- Add package directory for utilities (internal monorepo package)
- Move or mirror shared helper module into package namespace
- Ensure consumers can import from package namespace
- Add package-level tests and basic README
- Add release instructions (manual or CI-assisted)

## Out of Scope
- Publishing unrelated strategy logic
- Refactoring all strategy modules into packages
- Introducing non-essential feature changes to helper behavior
- Auto-release orchestration beyond minimal viable workflow

## Repo Touchpoints
- `strategies/common/strategy_artifacts.py`
- `strategies/common/__init__.py`
- `strategies/bear_es_sweep_1h_baseline.py`
- `strategies/bear_nq_sweep_1h_baseline.py`
- `tests/unit/test_strategy_artifacts.py`
- `pyproject.toml`
- `qws_graph/epics/unsorted_stories/`

## Implementation Notes
- Use `src/` package layout to avoid import shadowing issues
- Keep API surface small and explicit (`parse_*`, CSV normalization, CSV writer)
- Start with internal package usage, then publish once API is stable
- Include semantic versioning guidance in package README
- Validate wheels/sdists locally before first upload

## Acceptance Criteria
- [ ] A dedicated package directory exists with valid `pyproject.toml`
- [ ] Shared helpers are importable from package namespace
- [ ] Existing strategy scripts run using package imports without behavior change
- [ ] Package tests pass in CI/local runs
- [ ] Build artifacts (`sdist`, `wheel`) are generated successfully
- [ ] TestPyPI publish path is documented and validated

## Validation
- Run unit tests for shared helper behavior
- Run strategy script `--help` smoke checks after import switch
- Build package with `python -m build`
- Verify distribution metadata with `twine check`
- Perform TestPyPI upload dry run or actual test publish

## Definition of Done
- [ ] Package scaffold merged
- [ ] Consumers migrated to package import path
- [ ] Tests green and build validated
- [ ] Publish runbook committed
- [ ] Story marked CLOSED after successful validation

## Dependencies
- Depends on: internal helper extraction story completion
- Enables: cross-repo reuse of strategy utilities
- Enables: PyPI release and versioned dependency management

## Notes
This story should prioritize minimal, stable packaging of existing helpers before broadening scope to additional strategy modules.

