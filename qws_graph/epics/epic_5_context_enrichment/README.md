# Epic 5 — Context Enrichment

## Objective
Add the two missing data context dimensions — strategy family identity and market regime —
and build the comparative queries they enable. Without these, every run exists in isolation:
no cross-instrument view, no regime-conditional filtering, no multi-generation lineage.

## Why it exists
After Epic 4, the graph can track what happened and what was decided. Epic 5 answers
"under what conditions?" and "how does it compare?" These are the prerequisite questions
for any comparative research workflow.

Two concrete blockers exist today:
1. `family_id` is NULL on all Strategy nodes — shell runners never pass `--source-file`,
   so the cross-instrument grouping key is never computed. This blocks every cross-strategy
   query that groups by logic type.
2. Runs have no regime label — there is no way to query "show me champions that performed
   during high-volatility periods" because that context was never recorded.

## Stories in execution order
1. `QWS-0501` `story_1_family_id_population.md` — fix runners to populate `family_id`
2. `QWS-0502` `story_2_regime_tagging.md` — `--regime` flag, `regime` property on Run
3. `QWS-0503` `story_3_cross_instrument_aggregator.md` — `compare_strategy_performance` preset
4. `QWS-0504` `story_4_recursive_lineage_traversal.md` — depth param on `downstream_champions`

Story 2 is independent of Story 1. Stories 3 depends on Story 1 and Epic 4 QWS-0402
(OOS metrics must be stored at `qw record --oos` time for the OOS Sharpe column to work).
Story 4 is independent of all others.

## Dependencies
- Epic 3 complete (clean ingest pipeline).
- Epic 4 QWS-0402 (OOS outcome tracking) before Story 3 can surface OOS Sharpe.
- No Epic 6 dependency — this epic is a prerequisite for Epic 6 Story 1 comparative queries.

## Exit Criteria
- `family_id` is non-null on all Strategy nodes after a pipeline run.
- `qw query --name compare_strategy_performance` returns a populated table grouping
  champions by logic type across instruments.
- `qw record --regime high_vol` stores `regime` on the ingested Run nodes.
- `qw query --name downstream_champions --param depth=3` traverses multi-generation chains.
