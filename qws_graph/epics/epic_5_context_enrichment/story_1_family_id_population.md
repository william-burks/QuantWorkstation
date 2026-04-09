# Story 1 — Family ID Population

## ID
QWS-0501

## Status
READY

## Summary
Fix the four production shell runners to pass `--source-file` at ingest time so that
`family_id` is computed and stored on every Strategy node. Currently `family_id` is NULL
on all Strategy nodes because no runner passes this flag.

## Problem
`family_id` was introduced in Epic 2 as the cross-strategy grouping key — a hash derived
from `logic_type`, `direction`, and a source file hash. It enables queries like
`cross_artifact_correlation` and is the prerequisite for the `compare_strategy_performance`
preset planned in QWS-0503.

Since no shell runner passes `--source-file`, `family_id` is NULL on every live Strategy
node. The `cross_artifact_correlation` preset returns empty results for all strategies.
This was flagged as an open question in the Story 7 (QWS-0307) UAT runbook.

## Fix
Each of the four production runners passes `--source-file <strategy_script_path>` to
`qw record`. The CLI computes `source_hash = hash12(file_content)` and sets
`family_id = hash12(logic_type, direction, source_hash)` on the Strategy node.

**Runners to update:**
- `research/bin/run_liquidity_sweep_baseline.sh`
- `research/bin/run_liquidity_sweep_position_sizing.sh`
- `research/bin/run_liquidity_sweep_golden.sh`
- `research/bin/run_btc_mars_golden.sh`

Each runner already knows its strategy script path — it passes it to Python directly.
The `--source-file` flag just needs to reference the same path.

## In Scope
- Add `--source-file <path>` to `qw record` call in each of the four runners above.
- Verify `family_id` is non-null on Strategy nodes after a pipeline run.
- No changes to `cli.py`, `store.py`, or `parsers.py` — `--source-file` handling exists.

## Out of Scope
- `run_es_phase2.sh` and other isolation/exploration runners (research-only; not production
  pipeline runners).
- Backfilling `family_id` on existing Strategy nodes (will be set on next pipeline run
  via MERGE semantics).

## Repo Touchpoints
- `research/bin/run_liquidity_sweep_baseline.sh` — add `--source-file`
- `research/bin/run_liquidity_sweep_position_sizing.sh` — add `--source-file`
- `research/bin/run_liquidity_sweep_golden.sh` — add `--source-file`
- `research/bin/run_btc_mars_golden.sh` — add `--source-file`

No changes to `cli.py`, `store.py`, or `parsers.py` — `--source-file` confirmed present and working.

## Acceptance Criteria
- [ ] All four production runners pass `--source-file` to `qw record`.
- [ ] After a fresh pipeline run, `MATCH (s:Strategy) WHERE s.family_id IS NULL RETURN count(s)`
  returns `0` for strategies ingested by the four runners.
- [ ] `qw query --name cross_artifact_correlation --param strategy_id=cl-1h-bear-liquidity-sweep`
  returns non-empty results.

## Definition of Done
- [ ] Four runners updated.
- [ ] Neo4j spot-check confirms `family_id` present on Strategy nodes.
- [ ] Story marked CLOSED.
