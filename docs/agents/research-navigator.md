# research-navigator

**Model:** Opus 4.6 | **Role:** Graph-aware session manager, direction synthesis, pivot analysis

The session orchestrator. Reads the research graph, synthesizes the next direction shortlist,
enforces the BRANCHED_FROM requirement on pivots, and wraps sessions with findings.

---

## Invocation

```
/research-session
Phase 1: session start
```

Or spawn directly: `Use the research-navigator agent. [phase instruction]`

---

## Phase 1 — Session Start

**When:** Opening a session. No context yet.

**What happens:**
1. Reads agent memory for project context
2. Runs four preset queries: `recent_champions`, `former_champions`, `list_aborted`, `queued_hypotheses`
3. Scans `research/ideas/` for unprocessed raw ideas
4. Returns a ranked shortlist — not raw table dumps

**Example output:**
```
## Session Brief

### Graph State
4 Champions (2 OOS fail, 2 OOS pending) | 1 queued | 6 aborted

### Next Direction Shortlist
1. OOS validation — btc-4h-bear-rsi-bounce-short (17d8c702b421)
   Champion, OOS fail — investigate drawdown before any further BTC bear work
2. Queued hypothesis — cl-1h-bull-ema-tighter-stop (f4a91b3c8e22)
   Branched from 9f2e4a71c3b8 — parent had viable signal, DD 12.3% too high
3. New direction — CL bull side unexplored

### Unprocessed Ideas
- research/ideas/2026-04-10-vol-regime-filter.md (status: raw)

### Strategist Available
NO — no confirmed OOS champion yet

### Starting Point
Recommend: queued hypothesis cl-1h-bull-ema-tighter-stop — parent showed signal, just needs tighter stops
```

You decide. Navigator presented options; you pick.

---

## Phase 2 — Pre-Commit Redundancy Check

**When:** You have a hypothesis and want to log it before generating a trial.

```
Navigator: I want to test BTC 1H mean-reversion on high-volume reversals in bear regime
```

**What happens:**
1. Logs via `qw record --hypothesis` — returns a `hypothesis_id`
2. Runs `qw query --name check_redundancy --param hypothesis_id=<id>` silently
3. No match: hypothesis is live, passes you the ID
4. Match found:
   ```
   REDUNDANCY: abc123 — similar to btc-1h-mean-reversion logged 2026-03-14
   Prior outcome: ABORTED (N=8 trades IS — insufficient sample)
   Logged as def456. Confirm override? (y/n)
   ```

If you decline: navigator marks the new hypothesis aborted with a findings note linking it to the prior attempt.
The node exists in the graph as a record that you checked — not wasted work.

If no match: navigator hands you the `hypothesis_id`. Take it to trial-engineer.

---

## Phase 3 — Mid-Session Pivot

**When:** A trial result comes back and you need to decide next step.

```
Navigator: research/results/futures/ema_crossover/runs/20260414-161204/
```

**What happens:**
1. Reads bundle.json at that path
2. Compares against research targets (Sharpe ≥ 2.0, MaxDD ≤ 10%)
3. Returns a verdict:

```
## Pivot Analysis — 20260414-161204

Metrics: Sharpe IS=1.8 | MaxDD=12.3% | WinRate=47%
Target:  Sharpe IS≥2.0  | MaxDD≤10%

Verdict: BRANCH

Reason: Direction looks right (N=89, WinRate 47%) but DD 12.3% too high —
        signal is viable, stops too loose

BRANCHED_FROM: Trial 9f2e4a71c3b8
Rationale: "CL bull EMA cross passes N and direction but DD 12.3% → tighten stops"
```

Verdicts: `CONTINUE` (both pass) | `BRANCH` (one passes) | `ABANDON` (both fail)

**BRANCHED_FROM is non-optional on BRANCH verdict.** Navigator states the source node and
rationale. You approve before it creates the edge.

---

## Phase 4 — Session Wrap

**When:** Done for the session.

```
Navigator, wrap up. Hypothesis f4a91b3c8e22. Outcome: BRANCH.
Key finding: CL bull EMA cross viable signal (N=89) but stops need tightening — queued tighter stop variant.
```

**What happens:**
1. Updates `findings` on the hypothesis
2. Writes session notes to `research/ideas/session_YYYY-MM-DD.md`
3. Returns what to start with next session

---

## qw CLI Reference

| Command | Purpose |
|---|---|
| `qw query --name recent_champions` | Last 5 promoted champions |
| `qw query --name list_aborted` | All aborted hypotheses with findings |
| `qw query --name queued_hypotheses` | Hypotheses logged but not yet trialed |
| `qw query --name check_redundancy --param hypothesis_id=<id>` | Similarity check |
| `qw record --hypothesis "<text>" --source user` | Log a new hypothesis |
| `qw record --hypothesis <id> --findings "<text>"` | Update findings on existing |
| `qw record --hypothesis "<text>" --queue` | Log + mark as queued (don't run yet) |

---

## Boundaries

| Can | Cannot |
|---|---|
| `qw query --name <preset>` | Execute trial scripts |
| `qw record --hypothesis` | `qw record --bundle` |
| Write to `research/ideas/` | Write anywhere else |
| Read any file | `qw abort`, `qw champion`, `qw retire` |

---

## Common Mistakes

**Skipping Phase 2:** Jumping to `qw record --hypothesis` without the navigator's check risks
logging a hypothesis already tried and abandoned.

**Not queuing mid-session ideas:** If a new hypothesis surfaces while a trial is running, use
`qw record --hypothesis "<idea>" --queue` immediately. Navigator surfaces it at next session start.
