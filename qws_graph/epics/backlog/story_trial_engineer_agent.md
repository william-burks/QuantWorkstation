> **SUPERSEDED** — Active canonical story: `qws_graph/epics/epic_agent_design/story_QWS-1303_trial_engineer_agent.md`
> Do NOT implement from this file — agents searching by name will find the canonical story first.

# Story 3 — Trial Engineer Agent

## ID
QWS-1303

## Status
TESTING

## Blocked On
QWS-0902 CLOSED

## Summary
Create `.claude/agents/trial-engineer.md` — a Sonnet-model agent that writes trial scripts,
runs backtests, and ingests results via `qw record --bundle`. Create
`.claude/scripts/agent-trial-guard.sh` to block writes to execution, collectors, and
experiments modules, and to block champion lifecycle commands. Reports raw metrics only —
does not interpret results.

## Problem
Trial execution and graph ingestion currently require manual shell work across multiple
commands. There is no agent scoped to "write trial → run → ingest" that knows the right
interface (strategies/base.py), the right standards (standards.py), and the right post-run
action (`qw record --bundle`). Without this agent, Will must either do it manually or spawn
a general-purpose agent with no guardrails.

## Goal

```zsh
# Navigator hands direction to trial-engineer:
# "Write trial for CL 1h mean-reversion post-EIA, hypothesis H-042"

# trial-engineer:
# 1. reads strategies/base.py for interface
# 2. reads research/experiments/standards.py for thresholds — never hardcodes
# 3. checks existing trial numbers in research/trials/
# 4. writes research/trials/NN_cl_eia_mean_reversion.py
# 5. runs python research/trials/NN_cl_eia_mean_reversion.py
# 6. runs qw record --bundle research/results/.../runs/<timestamp>/
# 7. reports raw metrics: sharpe, max_dd, n_trades, active_window_frequency
# 8. does NOT interpret or recommend promotion — reports numbers only
```

## Agent Definition

**Model:** `claude-sonnet-4-5` (or latest Sonnet)
**Tools:** `Bash`, `Read`, `Write`, `Edit`, `Grep`, `Glob`
**Memory:** project
**Effort:** high
**Skills:** [caveman]

### Hard Rules (in agent definition body)
- Before writing any trial: read `strategies/base.py` for the `generate_signals()` interface
- Before writing any trial: read `research/experiments/standards.py` for promotion thresholds
- NEVER hardcode thresholds — import from `research/experiments/standards.py`
- Trial filenames are permanent: `NN_description.py` — check existing numbers in
  `research/trials/` before choosing N
- After backtest completes: run `qw record --bundle <results_dir>` to ingest
- CANNOT touch `execution/` — no writes to OMS, risk engine, or broker wrappers
- CANNOT touch `data/collectors/` — no writes to data collection scripts
- CANNOT commit or push
- CANNOT promote or demote champions — does NOT call `qw champion`, `qw degrade`, `qw retire`
- Does NOT interpret results — reports raw metrics (sharpe, max_dd, n_trades,
  active_window_frequency, calmar) and stops. Navigator or Will makes the call.

### Guard Script Blocks
`.claude/scripts/agent-trial-guard.sh` blocks:
- Writes to `execution/` (any file path under execution/)
- Writes to `data/collectors/` (any file path under data/collectors/)
- Writes to `research/experiments/*.py` (experiment harness is stable — do not modify)
- `qw abort`
- `qw degrade`
- `qw retire`
- `git commit`
- `git push`

### Guard Script Allows (explicitly)
- `python research/trials/` (trial execution)
- `python research/bin/` (shell runners)
- `qw record --bundle` (ingest only)
- `qw query` (read-only graph queries)

### Hook Registration
PreToolUse Bash, Write, Edit matchers → `agent-trial-guard.sh`

## In Scope
- `.claude/agents/trial-engineer.md` — full agent definition
- `.claude/scripts/agent-trial-guard.sh` — guard script following agent-guard.sh pattern

## Out of Scope
- Any graph schema changes
- Any CLI changes
- Strategy interpretation or promotion recommendation (agent reports numbers, Will decides)
- Research session command rewrite (QWS-0904)

## Repo Touchpoints
- `.claude/agents/trial-engineer.md` (new)
- `.claude/scripts/agent-trial-guard.sh` (new)

## Acceptance Criteria
- [ ] `.claude/agents/trial-engineer.md` exists with correct frontmatter
- [ ] Agent body mandates reading `strategies/base.py` and `standards.py` before writing trial
- [ ] Agent body prohibits hardcoded thresholds, writes to execution/ and data/collectors/,
  and champion lifecycle commands
- [ ] Agent body requires `qw record --bundle` after every successful backtest
- [ ] Agent body states "reports raw metrics only — does not interpret or recommend promotion"
- [ ] `.claude/scripts/agent-trial-guard.sh` exists, is executable, blocks all prohibited
  write paths and commands (test: echo each blocked pattern, verify exit 2)
- [ ] Guard script allows `python research/trials/`, `qw record --bundle`, `qw query`
- [ ] Hook registered in agent definition under PreToolUse Bash, Write, Edit matchers

## Definition of Done
- [ ] `trial-engineer.md` agent definition present and correctly formed
- [ ] `agent-trial-guard.sh` present, executable, blocks all prohibited patterns
- [ ] Manual smoke test: spawn trial-engineer with a direction, verify it reads base.py +
  standards.py before writing, verify it runs `qw record --bundle` after run
- [ ] All tests pass (`make verify` passes)
- [ ] Story marked CLOSED
