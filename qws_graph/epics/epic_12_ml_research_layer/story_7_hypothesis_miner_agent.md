# Story 7 — Hypothesis Miner Agent

## ID
QWS-1207

## Status
PLANNED

## Blocked On
QWS-1206 (results interpreter — miner benefits from verdict files as additional evidence),
graph maturity (more runs = better mining; useful only after ≥ 10 run nodes with IS/OOS
data in graph)

## Summary
New `/mine-ml-hypotheses` skill (or agent definition). Surveys graph state and proposes ML
hypotheses grounded in prior failure patterns. Reads graph via MCP. Writes proposal files
to `research/ideas/` with status `raw`. Every claim must cite specific graph node IDs.
Proposals without citations are rejected. `qw record --hypothesis` requires Will's manual
execution — agent proposes only.

## MCP Tools Read
`former_champions` (cause-of-death), `list_aborted`, `regime_performance` (regime-conditional
failures), `run_history` IS/OOS gaps, `similar_hypotheses` (dedup)

## Proposal File Format
```yaml
---
id: <generated slug>
status: raw
source: hypothesis_miner
evidence:
  - node_type: <Run|Strategy|Champion|FormerChampion>
    node_id: <id>
    observation: <one-line finding>
hypothesis: <ML hypothesis statement>
suggested_model_class: <hmm|lightgbm>
suggested_features: [<feature names>]
dedup_check: <similar_hypotheses query result summary>
---
```

## Key ACs
- Every proposal includes ≥ 1 cited node ID in `evidence` list. Agent rejects its own
  proposals lacking citations — does not write them.
- Agent runs `similar_hypotheses` before writing each proposal; includes result summary in
  `dedup_check`. If semantic similarity > 0.85 to an existing hypothesis, flags as
  `DUPLICATE` and skips write.
- Proposal files written to `research/ideas/` only. No graph writes.
- `qw record --hypothesis` is explicitly documented in skill as the manual next step.

## Repo Touchpoints
- `.claude/commands/mine-ml-hypotheses.md` — new skill file
- `research/ideas/` — directory exists from QWS-0901 (if closed); create if not
