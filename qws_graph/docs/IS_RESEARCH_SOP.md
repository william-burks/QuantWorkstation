```markdown
# IS Research Cycle — Standard Operating Procedure

**Version**: 1.0  
**Date**: April 1, 2026  
**Based on**: Bear CL sweep + Bull Q1 CL sweep investigations

---

## Overview

Every strategy investigation follows the same five-phase cycle.
No phase is skipped. No OOS run happens without completing all five.

```
Phase 1: Baseline Run
Phase 2: Signal Isolation
Phase 3: Focused Grid Search
Phase 4: Champion Freeze
Phase 5: OOS Preparation
```

---

## Phase 1 — Baseline Run

**Goal**: Understand what the raw strategy does before any tuning.

### Steps
1. Run the strategy with default parameters, no filters
2. Print the full funnel report (sweeps → trades)
3. Print session breakdown
4. Print wick size quartile table
5. Print monthly P&L

### Required Outputs
- [ ] Sample size (must be ≥ 20 to proceed)
- [ ] Win rate vs breakeven threshold
- [ ] Session breakdown (which sessions contribute)
- [ ] Wick quartile table (which quartiles contribute)
- [ ] Monthly consistency (how many months positive)

### Decision Gate
| Outcome | Action |
|---|---|
| Win rate ≥ breakeven | Proceed to Phase 3 (skip Phase 2) |
| Win rate < breakeven but signals visible | Proceed to Phase 2 |
| Win rate < breakeven, no visible signal | **Stop. Document failure. Archive.** |

### Document
Write one paragraph: what the baseline shows, what the most interesting signal is, what the obvious failure mode is.

---

## Phase 2 — Signal Isolation

**Goal**: Find the subset of the strategy that actually works.

### Rules
- Test **one variable at a time**
- Each test must maintain **n ≥ 20** (or document why lower is acceptable)
- Each test must have a **reason before running** — no fishing

### Isolation Axes (in priority order)
1. **Session filter** — which sessions carry the signal?
2. **Wick quartile filter** — which sweep sizes work?
3. **Direction** — does the signal invert on bull vs bear?
4. **Timeframe** — does the sweep timeframe matter?

### For Each Isolation Test, Record
```
Hypothesis: [what you expect and why]
Config change: [single parameter changed]
Result: [n, win rate, avg R, Sharpe]
Verdict: [keep / reject / investigate further]
```

### Decision Gate
- Isolated signal shows **win rate improvement** AND **positive avg R**
- If no isolation test improves the baseline → **Stop. Document. Archive.**

---

## Phase 3 — Focused Grid Search

**Goal**: Find the optimal parameter combination within the isolated signal space.

### Rules
- Grid axes must be **motivated by Phase 2 findings** — not exhaustive search
- Maximum **2 free parameters** in any single grid (avoid overfitting)
- Every config in the grid must be **explainable** — why would this work?

### Standard Grid Axes for This Architecture
| Axis | Typical Range | Notes |
|---|---|---|
| `target_r` | 0.75, 1.0, 1.25, 1.5 | Lower = higher hit rate |
| `min_r_dist` | 0.10, 0.15, 0.20 | Higher = cleaner entries |
| `wick_mode` | none, exclude_q2, q1_only, q3_q4_only | From Phase 2 |
| `stop_mode` | sweep_atr, 5m_lower_high | Test independently |
| `max_hold_bars` | 12, 24, 36 | Rarely needs changing |

### Required Outputs
- Full grid CSV saved to `results/`
- Analyzed with `analyze.py --min-n 20`
- Champion identified by **Sharpe among gate-passers**

### Gates for Champion Selection
| Gate | Minimum |
|---|---|
| Sample size | ≥ 20 |
| Total R | > 0 |
| Profit factor | ≥ 1.10 |
| Max drawdown | ≥ -12R |

### Decision Gate
- At least one config passes all four gates → promote to Phase 4
- No config passes gates → return to Phase 2 with new axis, or **Stop**

---

## Phase 4 — Champion Freeze

**Goal**: Lock the kernel. No more IS tuning.

### Steps
1. Record the champion config in full (every parameter, explicit)
2. Record the backup config (typically same but one parameter relaxed)
3. Run a clean single-backtest on champion to confirm numbers match grid
4. Write the champion markdown file (see template below)
5. Register in `registry.json`

### Champion Markdown Template
```markdown
# [STRATEGY_NAME]

## Config
- Direction: [BULL/BEAR]
- Sessions: [list]
- Sweep timeframe: [1H/4H/etc]
- wick_mode: [value]
- target_r: [value]
- min_r_dist: [value]
- stop_mode: [value]
- max_hold_bars: [value]

## IS Metrics
- Sample size: [n]
- Win rate: [x] (breakeven: [y])
- Avg R/trade: [x]
- Total R: [x]
- Profit factor: [x]
- Sharpe: [x]
- Max drawdown: [x]

## Why This Works
[1-2 sentences on the structural thesis]

## Known Fragilities
[Honest list of what could break this in OOS]

## OOS Command
[exact shell command to run OOS]
```

### What Freeze Means
- **No parameter changes** after this point
- **No re-running IS** on same data with new ideas
- If a new idea emerges → start a **new IS experiment** on fresh data

---

## Phase 5 — OOS Preparation

**Goal**: Everything needed to run OOS is ready before closing the IS session.

### Required Before Closing
- [ ] OOS harness script written and tested
- [ ] OOS window dates defined (chronologically after IS end)
- [ ] Backup config included in harness
- [ ] Pass/fail gates written into harness (not evaluated manually)
- [ ] Output saved to `results/` automatically

### OOS Pass/Fail Gates (Standard)
| Gate | Minimum |
|---|---|
| Sample size | ≥ 20 (or documented lower bound) |
| Total R | > 0 |
| Profit factor | ≥ 1.10 |
| Max drawdown | ≥ -12R |

### Promotion Rule
- Pass if **2 out of 3** OOS windows meet minimum gates
- If candidate and backup both pass → prefer higher median OOS Sharpe

### Decision Rule: Write It Before You See the Numbers
Before running OOS, write down:
```
If [metric] is [threshold], I will [action].
I will not adjust this decision after seeing results.
```

---

## Failure Documentation Template

When a strategy or phase fails, document it before moving on.

```markdown
# [STRATEGY_NAME] — FAILED

**Date**: [date]
**Phase failed**: [1/2/3]
**Failure mode**: [what specifically failed]
**What was tried**: [list of isolation attempts]
**Why it failed**: [structural thesis, not bad luck]
**Lesson**: [one sentence for future investigations]
**Archive location**: [path]
```

Failures are not wasted work. They are documented constraints on the search space.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Dangerous |
|---|---|
| Running OOS before freezing champion | Leaks OOS into tuning decisions |
| Stacking multiple filters before testing each alone | Can't attribute improvement |
| Adjusting gates after seeing OOS results | Defeats the purpose of gates |
| Continuing IS tuning after Phase 4 | Data mining, not research |
| Dropping a fragility flag because "it probably won't matter" | Honest assessment is the whole point |
| Running grid with > 2 free axes | Exponential overfitting risk |

---

## Pipeline State Tracking

Maintain one entry per strategy in `registry.json`:

```json
{
  "strategy_id": "bear_cl_1h_nypre_after",
  "status": "oos_pending",
  "is_complete": true,
  "oos_windows_passed": 0,
  "oos_windows_run": 0,
  "tier": "professional",
  "trades_per_month_estimate": 2,
  "champion_file": "strategies/bear_cl_sweep_1h_baseline.py"
}
```

Status values: `is_research` → `oos_pending` → `oos_passed` → `live_paper` → `live` → `failed` → `archived`

---

## Session Checklist

At the end of every research session, answer these before closing:

- [ ] Is every experiment result saved to `results/`?
- [ ] Is there a markdown note for this session?
- [ ] Is the champion (if found) frozen and documented?
- [ ] Is the OOS harness ready to run without modification?
- [ ] Is the pipeline state in `registry.json` up to date?
- [ ] Have I written down the honest fragilities of any new signal?

If any box is unchecked, finish it before closing.
```