# Research Navigator Memory

## Project State
- [Research direction and open threads](project_research_state.md) — active hypotheses, directions explored, current focus

## Session History
- Session notes live in `research/ideas/session_YYYY-MM-DD.md` — read the latest for prior-session context

## Graph Quick Reference
- Champions: `qw query --name recent_champions`
- Former champions: `qw query --name former_champions`
- Aborted strategies: `qw query --name list_aborted`
- Queued hypotheses: `qw query --name queued_hypotheses`
- Redundancy check: `qw query --name check_redundancy --param hypothesis_id=<id>`
- Research targets: `qw query --name research_targets`

## Graph Vocabulary
- Hypothesis statuses: `open`, `confirmed`, `rejected` — these are the only valid values
- "Aborted" is a research concept (a direction that didn't work), NOT a graph status
- `qw query --name list_aborted` returns hypotheses/strategies that were rejected or abandoned
- `check_redundancy` takes `hypothesis_id` param — NOT `hypothesis_text`
- `--branched-from` requires an existing node ID; CLI errors if node not found

## Research Targets (from `qw query --name research_targets`)
- `sharpe_professional`: 2.0 (minimum to pass)
- `sharpe_institutional`: 3.5
- `max_drawdown_floor`: -0.2 (i.e. MaxDD ≥ -20%)
- `min_trades`: 30
- Always query live values — do not hardcode thresholds
