# Story 6 — Results Interpreter Agent

## ID
QWS-1206

## Status
PLANNED

## Blocked On
QWS-1204 (ML walk-forward output format must be stable before interpreter can parse it)

## Summary
New `/interpret-ml-results` skill (or agent definition). After a training run completes,
reads structured output and produces a verdict file at
`research/results/<experiment_id>/verdict.md`. Reads experiment output dir + graph via
MCP tools. Mechanical thresholds only — never writes to graph, never promotes.

## Verdict Outputs
Per-fold metric table, IS/OOS gap assessment, fold stability (Sharpe stdev), feature
concentration check, correlation to existing Champions (redundancy gate), monotonic decay
check. Final verdict: one of `PROMOTION_CANDIDATE | NEEDS_REVIEW | OVERFIT |
INSUFFICIENT_SAMPLE | FAIL`.

## Hard Gates
| Condition | Verdict |
|---|---|
| OOS Sharpe < 2.0 | FAIL |
| IS/OOS Sharpe ratio > 2.0 | OVERFIT |
| Correlation to Champion > 0.30 | REDUNDANT (sub-verdict of NEEDS_REVIEW) |
| OOS trades < 60 | INSUFFICIENT_SAMPLE |
| Top-3 features > 80% importance | FRAGILE flag (appended to any verdict) |
| Sharpe declines 3+ consecutive folds | MONOTONIC_DECAY flag |

## MCP Tools Read
`recent_champions`, `former_champions`, `regime_performance`, `portfolio_alpha`

## Key ACs
- Verdict file written to `research/results/<experiment_id>/verdict.md`; includes
  experiment_id, run timestamp, all gate results, final verdict string.
- Agent reads output CSV from `ml_walk_forward.py`; fails with clear message if CSV absent.
- No graph writes. No `qw record` calls. Read-only.
- All gate thresholds match architect spec above — no soft defaults.
- `ruff check` and `mypy --strict` pass on any Python components.

## Repo Touchpoints
- `.claude/commands/interpret-ml-results.md` — new skill file
- `research/results/` — output directory convention documented
