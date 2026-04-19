# trial-engineer

**Model:** Sonnet 4.6 | **Role:** Hypothesis → trial script + bundle.json → raw metrics

Accepts a structured input contract, generates the trial script and bundle template, then stops.
After explicit "run it": executes, ingests, and reports raw metrics. Never interprets results.

---

## Invocation

```
Use the trial-engineer agent.
[input contract]
```

---

## Input Contract

Six required fields. Missing any one blocks execution.

```
hypothesis_id: abc123def456       # from qw record --hypothesis (Phase 2 of navigator)
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

---

## Before Writing

Agent always does three reads before writing anything:

1. `strategies/base.py` — confirms `generate_signals()` signature; matches it exactly
2. `research/experiments/standards.py` — imports thresholds; never hardcodes them
3. `ls research/trials/<asset>/<strategy>/` — determines next sequential NN

---

## Output (before run)

```
Generated: research/trials/<asset>/<strategy>/NN_<description>.py
Bundle template: research/trials/<asset>/<strategy>/bundle.json
Review, then run: python -m research.trials.<asset>.<strategy>.NN_<description>
```

**STOPS HERE.** Does not execute until you say "run it".

---

## Running the Trial

Review the generated script. If it looks right:

```
run it
```

Agent executes, ingests via `qw record --bundle`, and reports:

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

**STOPS HERE.** Does not interpret. Does not recommend promotion.
Take the run ID to research-navigator Phase 3 for pivot analysis.

---

## Trial Filename Convention

Format: `NN_description.py` — permanent, never renumber.
Results reference by filename. N = max existing NN + 1 in that directory.
Guard blocks write if proposed N ≠ max + 1.

---

## Boundaries

| Can | Cannot |
|---|---|
| Write to `research/trials/` | Write to `execution/`, `data/collectors/`, `util/` |
| Write to `research/results/` | Modify `research/experiments/*.py` |
| Execute trial scripts (after "run it") | Execute without explicit "run it" |
| `qw record --bundle` (after run, with hypothesis_id) | `qw record --bundle` without `hypothesis_id` in bundle |
| `qw query` for context | `qw abort`, `qw champion`, `qw degrade` |
| Read any file | `git commit`, `git push` |

---

## Common Mistakes

**Giving trial-engineer no hypothesis_id:** The guard blocks `qw record --bundle` if
`hypothesis_id` is missing from bundle.json. Log the hypothesis in navigator Phase 2 first.

**Asking it to interpret results:** Raw metrics only. Phase 3 (navigator) gives the verdict.

**Expecting "run it" to trigger automatically:** Always stops after writing the script.
Say "run it" explicitly after reviewing the code.
