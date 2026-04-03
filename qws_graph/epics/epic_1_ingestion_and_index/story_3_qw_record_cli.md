# Story 3 — `qw record` CLI

## Status
ready

## Summary
Add the first graph integration command that validates and records artifact data without altering existing run commands.

## Problem
There is no standardized ingestion command to bridge artifact outputs and graph ledger writes.

## Goal
Implement `qw record` with contract-compliant flags, exit codes, and receipt generation.

## Inputs
- `docs/graph_v1_contract.md`
- Story 2 outputs (`models.py`, `parsers.py`)
- Existing CLI conventions in repo (`argparse` scripts)

## Deliverable
- `research/graph/cli.py`
- Optional CLI support files (`research/graph/receipts.py`)
- Console entrypoint in `pyproject.toml`

## In Scope
- `--file`, `--kind`, `--pivot-from`, `--offline`, `--dry-run`, timeout
- Exit codes 0/1/2 per contract
- Receipt file write to `.qws/receipts/`
- Pending write in offline mode to `.qws/pending/`

## Out of Scope
- `qw query` advanced presets
- MCP code
- Strategy script modifications

## Repo Touchpoints
- `research/graph/cli.py`
- `research/graph/receipts.py` (if separated)
- `pyproject.toml`
- `.qws/` runtime directories

## Implementation Notes
- Keep CLI behavior deterministic and explicit.
- Validation errors should be human-readable and machine-parsable enough for CI logs.
- `--dry-run` must not require Neo4j availability.

## Acceptance Criteria
- [ ] `qw record --help` documents contract flags.
- [ ] Validation failure returns exit code 1.
- [ ] Infra failure without offline returns exit code 2.
- [ ] Offline success returns exit code 0 and writes pending payload.
- [ ] Successful ingest writes receipt JSON.

## Validation
- CLI integration tests for success/failure/offline/dry-run paths.
- Manual smoke run with one baseline CSV and one champion markdown.

## Definition of Done
- [ ] CLI command wired and discoverable.
- [ ] Exit code contract verified by tests.
- [ ] Receipt and pending directories created automatically when missing.

## Open Questions
- None.

## Notes
This story must complete before shell hook integration.

