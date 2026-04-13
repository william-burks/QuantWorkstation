# Epic 9.5 — Workflow Hardening

## Objective
Fix researcher friction gaps discovered during Epic 9 — hypothesis lookup, ad-hoc queries,
trial metadata survival through bundle ingest, and CL historical data extension. All stories
are independent and can be implemented in parallel.

## Why it exists
Epic 9 strategy development sessions identified workflow gaps that slow down the research
loop: no easy way to browse hypotheses by status, no surgical Cypher passthrough for
one-off fixes, trial metadata columns being silently dropped on ingest, and insufficient
CL historical data for walk-forward validation. These don't require schema changes — just
targeted CLI additions and data pipeline fixes.

## Stories

| ID | Name | File | Status | Blocked On |
|---|---|---|---|---|
| QWS-0905 | Hypothesis lookup and findings | `story_QWS-0905_hypothesis_lookup_and_findings.md` | READY | — |
| QWS-0906 | Ad-hoc Cypher and patch | `story_QWS-0906_adhoc_cypher_and_patch.md` | READY | — |
| QWS-0907 | Trial metadata JSON blob | `story_QWS-0907_trial_metadata_json_blob.md` | READY | — |
| QWS-0908 | CL historical data extension | `story_QWS-0908_cl_historical_data_extension.md` | READY | — |
