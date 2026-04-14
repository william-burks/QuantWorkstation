# Agent User Manual — research-navigator + trial-engineer

Two agents shipped in Epic 13. This doc covers when to use each, how to invoke them,
what to expect, and worked examples using the live graph state.

---

## Overview

| Agent | Model | Role | When to Use |
|---|---|---|---|
| `research-navigator` | Opus | Reads graph, synthesizes direction, redundancy check, session wrap | Session start, mid-session pivots, session end |
| `trial-engineer` | Sonnet | Generates trial script + bundle.json from input contract, stops before run | After direction is chosen and you want code |

Neither agent makes trading decisions. Neither executes a backtest without explicit "run it."
You approve every handoff.

---

## research-navigator

### Invocation

```
/research-navigator
```

Or from a new Claude Code session where you want research guidance:
```
Use the research-navigator agent. [Phase instruction]
```

### Phase 1 — Session Start

**When:** Start of any research session. Know nothing yet.

**What it does:**
1. Reads agent memory for project context
2. Runs all four screening queries: `recent_champions`, `former_champions`, `list_aborted`, `queued_hypotheses`
3. Returns a ranked shortlist — not raw table dumps

**Example output (given current graph state):**

```
## Session Brief

### Graph State
4 Champions (2 OOS fail, 2 OOS pending) | 0 queued | 6 aborted

### Next Direction Shortlist
1. OOS validation — btc-4h-bear-rsi-bounce-short (17d8c702b421)
   Champion is OOS fail — needs drawdown investigation before any further BTC bear work
2. OOS validation — btc-4h-bull-rsi-pullback (b2a6d9624968)
   Champion is OOS fail — 5 trades IS is thin; regime filter too aggressive?
3. New CL direction — bear strategy is champion (0e992ad9452c) but Sharpe IS inflated
   4 trades only; needs more sample size before trusting

### Starting Point
Recommend: investigate OOS fail on btc-4h-bear-rsi-bounce-short — understand why before
starting new CL work
```

**You decide.** Navigator presented options; you pick which direction to pursue.

---

### Phase 2 — Pre-Commit Redundancy Check

**When:** You have a hypothesis and want to log it before running a trial.

**How:** Just tell the navigator the hypothesis text.

```
Navigator, I want to test: "BTC 1H mean-reversion on high-volume reversals in bear regime"
```

**What it does:**
1. Logs the hypothesis via `qw record --hypothesis` — returns a `hypothesis_id`
2. Runs `check_redundancy --param hypothesis_id=<id>` silently
3. Says nothing if no match — hypothesis is live, hand the ID to trial-engineer
4. Flags match if found:

```
REDUNDANCY: abc123 — similar to btc-1h-mean-reversion logged 2026-03-14 —
prior outcome: ABORTED (insufficient trades IS, N=8)
Logged as def456. Confirm override? (y/n)
```

**If you decline:** navigator marks the new hypothesis aborted with a findings note linking it to the prior attempt. Nothing wasted — the node is in the graph as a record that you checked.

**If no match:** navigator passes you the `hypothesis_id` and you hand it to trial-engineer.

---

### Phase 3 — Mid-Session Pivot

**When:** A trial result comes back and you need to decide next step.

**How:** Paste the bundle path or metrics.

```
Navigator: research/results/crypto/btc_donchian/runs/20260414-143022/
```

**What it does:**
1. Reads bundle.json at that path
2. Compares against research targets (Sharpe ≥ 2.0, MaxDD ≤ 10%)
3. Returns a verdict:

```
## Pivot Analysis — 20260414-143022

Metrics: Sharpe IS=1.4 | MaxDD=14.2% | WinRate=38%
Target:  Sharpe IS≥2.0  | MaxDD≤10%

Verdict: ABANDON

Reason: Both hurdles failed — Sharpe below threshold and DD exceeds 10% limit

Record failure:
qw record --hypothesis <id> --findings "Sharpe 1.4, DD 14.2% — fails both hurdles"
```

Or for a passing result with a drawdown problem:

```
## Pivot Analysis — 20260414-150312

Metrics: Sharpe IS=2.8 | MaxDD=15.1% | WinRate=52%
Target:  Sharpe IS≥2.0  | MaxDD≤10%

Verdict: BRANCH

Reason: Sharpe passes but DD 15% exceeds limit — suggests stops too loose

Queued alternatives:
[output of queued_hypotheses query]
```

**BRANCHED_FROM is non-optional on a BRANCH verdict.** Navigator names the source node,
rationale, and the edge to create. You approve before it proceeds.

---

### Phase 4 — Session Wrap

**When:** You're done for the session. Signal it:

```
Navigator, wrap up the session. Hypothesis worked: <id>. Outcome: CONTINUE.
Key finding: ATR filter improved drawdown but hit rate too low in bull regime.
```

**What it does:**
1. Updates `findings` on the hypothesis: `qw record --hypothesis <id> --findings "..."`
2. Writes session notes to `research/ideas/session_YYYY-MM-DD.md`
3. Tells you what to start with next session

```
Next session: resume hypothesis abc123 — add bull-regime ATR calibration
```

---

## trial-engineer

### Invocation

```
/trial-engineer
```

Or spawn directly: `Use the trial-engineer agent.`

### Input Contract

Trial-engineer needs 6 required fields. Give all six up front — missing fields block the run.

```
hypothesis_id: abc123def456       # from qw record --hypothesis output
instrument: CL
timeframe: 1H
trial_type: baseline
strategy_class: liquidity-sweep
entry_logic: short on bear candle after liquidity sweep above session high; 
             ATR filter applied; bear regime confirmed by 4H EMA slope
exit_logic: fixed 1.5 ATR stop, 3 ATR target
```

Optional:
```
config_overrides: {"atr_period": 20, "stop_multiplier": 1.5}
```

### What it generates

Trial-engineer does three things before stopping:

1. Reads `strategies/base.py` to confirm the `generate_signals()` signature
2. Reads `research/experiments/standards.py` to import thresholds (never hardcodes them)
3. Checks `ls research/trials/<asset>/<strategy>/` for next sequential NN

Then writes:
- `research/trials/futures/liquidity_sweep/12_bear_atrgated_short.py`
- `research/trials/futures/liquidity_sweep/bundle.json` (template with `hypothesis_id` pre-filled)

Output:
```
Generated: research/trials/futures/liquidity_sweep/12_bear_atrgated_short.py
Bundle template: research/trials/futures/liquidity_sweep/bundle.json
Review, then run: python -m research.trials.futures.liquidity_sweep.12_bear_atrgated_short
```

**STOPS HERE.** Does not execute.

### Running it

Review the generated script. If it looks right:

```
run it
```

Trial-engineer executes, ingests via `qw record --bundle`, and reports raw metrics:

```
Trial: 12_bear_atrgated_short.py
Run ID: 63bcef04a1d2
Sharpe (IS): 2.31
Max DD: 8.4%
N Trades: 47
Active Window Freq: 0.11
Calmar: 2.74
Passed dual-hurdle gate: yes
```

**STOPS HERE.** Does not interpret results, does not recommend promotion. Take the run ID back
to the navigator (Phase 3) for pivot analysis.

---

## Worked Example — Full Session

**Setup:** Starting fresh. Want to explore a new CL direction.

---

**Step 1 — Session start**

```
/research-navigator
Phase 1: session start
```

Navigator returns session brief. Current graph shows champion `cl-1h-bear-liquidity-sweep`
(Sharpe 27.9 IS — inflated, only 4 trades). Shortlist recommends investigating sample size
problem before new work.

You decide: **explore a CL bull strategy instead** (bear is thin, want directional diversity).

---

**Step 2 — Log the hypothesis + redundancy check**

Tell the navigator:

```
Navigator: I want to test CL 1H bull trend following on EMA crossover with ATR volatility gate
```

Navigator logs it and checks redundancy in one flow:
1. Runs `qw record --hypothesis "CL 1H bull trend follow: 20/50 EMA cross, long only, ATR < 1.5x 20D avg" --source user`
2. Runs `qw query --name check_redundancy --param hypothesis_id=<id>` silently
3. No match found — returns: `hypothesis_id: f4a91b3c8e22`

---

**Step 3 — Generate the trial**

```
/trial-engineer

hypothesis_id: f4a91b3c8e22
instrument: CL
timeframe: 1H
trial_type: baseline
strategy_class: ema-crossover
entry_logic: long when 20 EMA crosses above 50 EMA; ATR < 1.5x 20-day average ATR (volatility gate)
exit_logic: exit when 20 EMA crosses below 50 EMA; hard stop 2x ATR from entry
```

Agent generates `research/trials/futures/ema_crossover/01_baseline.py` and `bundle.json`.

Review the file. Looks right. Run:

```
run it
```

Result:
```
Trial: 01_baseline.py
Run ID: 9f2e4a71c3b8
Sharpe (IS): 1.8
Max DD: 12.3%
N Trades: 89
Active Window Freq: 0.18
Calmar: 1.46
Passed dual-hurdle gate: no
```

---

**Step 4 — Pivot analysis**

```
Navigator: research/results/futures/ema_crossover/runs/20260414-161204/
```

```
## Pivot Analysis — 20260414-161204

Metrics: Sharpe IS=1.8 | MaxDD=12.3% | WinRate=47%
Target:  Sharpe IS≥2.0  | MaxDD≤10%

Verdict: BRANCH

Reason: Trades and direction look right (N=89, WinRate 47%) but DD 12.3% too high —
        signal is viable, stops too loose

BRANCHED_FROM: Trial 9f2e4a71c3b8, rationale="CL bull EMA cross passes Sharpe threshold
marginally but DD 12.3% exceeds 10% limit — tighten stops to ATR-scaled exit"
```

You approve. Navigator creates the edge. Queue the tighter-stop variant:

```
qw record --hypothesis "CL 1H bull EMA cross: tighter stop 1.0 ATR from entry" \
  --branched-from 9f2e4a71c3b8 \
  --rationale "01_baseline hit 12.3% DD — ATR-scaled stop should bring it under 10%" \
  --queue
```

---

**Step 5 — Session wrap**

```
Navigator, wrap up. Hypothesis f4a91b3c8e22. Outcome: BRANCH.
Key finding: CL bull EMA cross viable signal (N=89) but stops need tightening — queued tighter stop variant.
```

Navigator writes session notes to `research/ideas/session_2026-04-14.md`.

```
Next session: resume queued hypothesis <new_id> — CL bull EMA cross tighter stop variant
```

---

## Reference — What Each Agent Can and Cannot Do

### research-navigator

| Can | Cannot |
|---|---|
| `qw query --name <preset>` | Execute trial scripts |
| `qw record --hypothesis` | `qw record --bundle` (no ingest) |
| Write to `research/ideas/` | Write anywhere else |
| Read any file | `qw abort`, `qw champion`, `qw retire` |

### trial-engineer

| Can | Cannot |
|---|---|
| Write to `research/trials/` | Write to `execution/`, `data/collectors/`, `util/` |
| Write to `research/results/` | Modify `research/experiments/*.py` |
| `python <trial>` (after "run it") | `qw abort`, `qw champion`, `qw degrade` |
| `qw record --bundle` (after run) | `qw record --bundle` without `hypothesis_id` in bundle |
| `qw query` for context | Commit or push |

---

## Common Mistakes

**Skipping Phase 2 (redundancy check):** If you jump straight to `qw record --hypothesis`
without the navigator's redundancy check, you may log a hypothesis that's already been tried
and abandoned. Always check first.

**Giving trial-engineer a direction without hypothesis_id:** The guard blocks `qw record --bundle`
if `hypothesis_id` is missing from bundle.json. Log the hypothesis first, get the ID, then
hand it to trial-engineer.

**Asking trial-engineer to interpret results:** It won't. Raw metrics only. Take the run ID
back to the navigator for verdict and pivot logic.

**Not queuing mid-session ideas:** If a new idea surfaces while a trial is running, don't lose
it to the chat context. Use `qw record --hypothesis "<idea>" --queue` immediately. The navigator
will surface it at the next session start.

**Expecting "run it" to trigger automatically:** Trial-engineer always stops after writing the
script. You must explicitly say "run it" — this is intentional so you can review the code first.
