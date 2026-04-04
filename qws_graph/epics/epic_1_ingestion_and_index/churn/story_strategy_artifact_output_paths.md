# Story: Strategy Script CSV Output Path Handling

## Status
CLOSED

## Problem
Strategy scripts in `strategies/bear_*_baseline.py` accept `--results-csv` path arguments but don't actually write CSV outputs to those custom paths. Shell hooks in Story 5 expect artifacts at paths like `results/es_phase2_session_nypre.csv`, but the strategy scripts don't emit files to these locations, blocking ingestion validation.

## Goal
Fix strategy scripts to reliably write CSV artifacts to the path specified by `--results-csv` argument in all execution modes.

## Deliverable
- Fix CSV output emission in both `strategies/bear_es_sweep_1h_baseline.py` and `strategies/bear_nq_sweep_1h_baseline.py`
- Ensure `--results-csv` path argument is honored in baseline run mode
- Ensure `--results-csv` path argument is honored in grid search mode
- Auto-create output directories if missing

## In Scope
- CSV file writing behavior in baseline strategy scripts
- Argument parsing and path handling for `--results-csv`
- Output directory creation
- Verification that files are written non-empty

## Out of Scope
- Changes to backtest logic or metric computation
- Changes to shell hook behavior (Story 5 owns that)
- Changes to graph ingestion or Neo4j write paths

## Repo Touchpoints
- `strategies/bear_es_sweep_1h_baseline.py`
- `strategies/bear_nq_sweep_1h_baseline.py`

## Implementation Notes
- Scripts already parse `--results-csv` via argparse
- Check both single-run and grid-search code paths for where CSV is written
- Use `pathlib.Path.mkdir(parents=True, exist_ok=True)` to auto-create directories
- Verify output files are non-empty before script completion

## Acceptance Criteria
- [x] CSV output is written to the path specified by `--results-csv` in baseline runs
- [x] CSV output is written to the path specified by `--results-csv` in grid search runs
- [x] Output directories are created automatically if missing
- [x] Scripts validate that output files are non-empty

## Validation
- Run baseline scripts with explicit `--results-csv` overrides and confirm files exist at specified paths
- Run grid search with explicit `--results-csv` override and confirm file exists
- Verify shell hooks can now find and ingest artifacts from hook-expected paths

## Definition of Done
- [x] Both baseline scripts write to `--results-csv` paths consistently
- [x] Output directories auto-created if needed
- [x] Strategy script CSV output paths are satisfied
- [x] Story 5 shell hooks can now complete receipt/pending validation

## Dependencies
- Unblocks: Epic 1 Story 5 (shell hooks receipt/pending ingestion)
- Related: Story "Shell Hook Race Condition on Artifact Flush" (timing safeguard)

## Notes
This is the primary blocker for Story 5's acceptance criteria. Once fixed, combined with the timing story, Story 5 can be fully validated.


