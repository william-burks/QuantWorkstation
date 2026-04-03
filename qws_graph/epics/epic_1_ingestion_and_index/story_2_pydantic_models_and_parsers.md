# Story 2 — Pydantic Models and Parsers

## Status
ready

## Summary
Implement strict-enough V1 artifact models and parsers for baseline CSV, grid CSV, and champion Markdown.

## Problem
Artifact data is currently human-readable but not normalized for deterministic graph ingestion.

## Goal
Create validated `ResearchArtifact` payloads from real repository outputs.

## Inputs
- `docs/graph_v1_contract.md`
- `results/*.csv`
- `research/results/champions/*.md`
- `research/results/registry.json`

## Deliverable
- `research/graph/models.py`
- `research/graph/parsers.py`
- Parser fixtures and tests under `tests/fixtures/artifacts/` and `tests/unit/`

## In Scope
- Pydantic models with `extra='ignore'`
- Required-field validation failures
- Unknown-field warning surface for CLI
- Parsing and normalization logic to contract shapes

## Out of Scope
- Neo4j write logic
- CLI command wiring
- Shell hooks

## Repo Touchpoints
- `research/graph/models.py`
- `research/graph/parsers.py`
- `tests/fixtures/artifacts/`
- `tests/unit/test_graph_parsers.py`

## Implementation Notes
- Reuse existing validation style from `research/candidate_validator.py`.
- Parse champion markdown conservatively; fail on missing required sections.
- Keep parser outputs deterministic (same artifact -> same payload ordering/values).

## Acceptance Criteria
- [ ] Baseline CSV parser returns one or more valid `Run` payloads.
- [ ] Grid CSV parser returns `Run` + `Config` payloads with deterministic config IDs.
- [ ] Champion parser returns valid `Champion` payload including `fragilities` list.
- [ ] Missing required columns/sections produce validation failure.
- [ ] Extra CSV columns are ignored and reported.

## Validation
- Run unit tests on parser and model modules.
- Validate at least one ES and one NQ artifact fixture.
- Confirm repeated parse returns identical normalized payload hash.

## Definition of Done
- [ ] Models and parsers committed with tests.
- [ ] Fixtures represent current repo artifact formats.
- [ ] Test suite passes for parser cases.

## Open Questions
- None; benchmark basket is deferred and not required for parser completion.

## Notes
This story unblocks `qw record` and store-layer implementation.

