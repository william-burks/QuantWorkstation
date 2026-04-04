# Story: Shell Hook Race Condition on Artifact Flush

## Status
CLOSED

## Problem
Shell ingestion hooks in Story 5 execute `qw record` immediately after strategy script completion. Python CSV writes may not have fully flushed to disk by the time the hook checks for the file, causing a race condition where the file exists in Python's buffer but not yet on filesystem.

## Goal
Add a small delay in the shell hook to allow CSV buffer flush to complete before attempting ingestion, making artifact detection reliable.

## Deliverable
- Update `record_artifact()` function in `research/run_es_nq_baseline.sh` to add `sleep 1` before artifact existence check
- Update `record_artifact()` function in `research/run_es_phase2.sh` to add `sleep 1` before artifact existence check
- Document the race condition and timing rationale in shell script comments

## In Scope
- Add timing delay in shell hooks before artifact ingestion attempts
- Ensure delay is transparent and does not interfere with script flow or exit codes

## Out of Scope
- Changes to strategy script CSV writing logic (separate story)
- Changes to qw record CLI behavior
- Neo4j write path changes
- Performance optimization of the sleep duration

## Repo Touchpoints
- `research/run_es_nq_baseline.sh`
- `research/run_es_phase2.sh`

## Implementation Notes
- Use `sleep 1` to give filesystem adequate time to sync
- Add inline comment explaining the race condition
- Delay occurs only after Python script completion but before hook execution
- Keep solution simple and repo-native (no external dependencies)

## Acceptance Criteria
- [ ] `record_artifact()` adds `sleep 1` before artifact existence check in both scripts
- [ ] Both shell scripts have the timing safeguard in place
- [ ] Hook still executes `qw record` with soft-fail (`|| true`) behavior after delay
- [ ] Script exit codes and flow control remain unaffected

## Validation
- Run shell script and confirm hook delay does not cause unexpected timeout
- Verify receipt/pending files are created when artifacts are present
- Measure that delay does not materially impact overall script runtime (should add ~1 second per hook call)

## Definition of Done
- [ ] Shell hooks patched with `sleep 1` safeguard
- [ ] Timing behavior verified in manual test runs
- [ ] Story 5 receipt/pending acceptance can be completed (when combined with strategy CSV fix)

## Dependencies
- Related: Story "Strategy Script CSV Output Path Handling" (CSV must actually be written)
- Unblocks: Epic 1 Story 5 (partial—still needs strategy script CSV fix for full validation)

## Notes
Timing-based race conditions are common in file I/O workflows. This safeguard addresses the delay between Python process exit and filesystem sync completion. An alternative would be polling with timeout, but simple delay is cleaner for research scripts.
