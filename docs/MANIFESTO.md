# MANIFESTO — North Star

> **LLM INSTRUCTION BLOCK**
> ```
> CONSTRAINTS:
>   - Sharpe target ≥ 2.0 (Professional) | ≥ 3.5 (Institutional)
>   - Max holding period ≤ 4 hours
>   - Optimize for alpha and risk-adjusted profitability — NOT win rate, NOT trend following
>   - Instruments: futures (ES, NQ, CL, MES, MNQ) and crypto (BTC) — short-duration edges
>
> BEFORE SUGGESTING a new strategy:
>   1. Call qw query --name recent_champions
>   2. Call qw query --name former_champions (check for reskins of dead edges)
>   3. If suggestion resembles a FormerChampion, state the similarity and cause-of-death explicitly
>
> AUTHORITY: Will is the Guiding Researcher and final decision-maker on all champion promotions.
>            You are the Navigator. Suggest, surface, and query — do not decide.
> ```

---

## Mission

Build a personal research exocortex for systematic trading: a permanent, queryable record of
every hypothesis, trial, and champion decision — shared across AI sessions, across models, and
across time.

Every trial leaves a record. Every champion earned its status through evidence. Every dead edge
teaches the next direction. No session starts cold.

---

## The Problem This Solves

### Context Drift
Each new session starts from zero. The same market inefficiencies get proposed again.
Redundant trials run. Promising pivots are forgotten because they were never written down
in a form a machine can query.

### Split-Brain Research
Ideation happens in one model (or one session), implementation in another. There is no shared
memory between sessions. Will manually bridges the gap — re-deriving context that already exists
somewhere, in some form, just not in a queryable graph.

### No Provenance
A current champion exists. But: what hypothesis produced it? What trials failed first?
What pivot decision led here? Without provenance, every strategy is an island — and the AI
cannot reason about why a direction was taken, only what currently exists.

---

## Core Philosophy

**The graph is the shared brain.** Any model that can call MCP tools reads from the same
Neo4j instance. Session context is a convenience layer. The graph is the truth.

**Champions earn status through evidence.** Promotion requires Sharpe ≥ 2.0 AND
evidence_score (Sharpe × √trades) exceeding the current champion. Opinion is not a gate.

**Former Champions are more valuable than you think.** They show how alpha dies.
An LLM that queries former_champions before suggesting is less likely to propose a
"new" variant that already decayed six months ago.

**Aborted strategies are closed branches, not deleted history.** When a strategy is
aborted (`qw abort`), its node is preserved with `status = ABORTED` and a mandatory
`abort_reason`. No new Trials or Champions can be attached. To revisit the logic, a
researcher must `BRANCH_FROM` it with a new Hypothesis that explicitly addresses the
original failure. This prevents "zombie strategies" — logic that was killed for good
reason but keeps re-emerging because the failure was never queryable.

**Pivots must leave a trace.** When a direction changes, a `BRANCHED_FROM` edge is created
linking the new Hypothesis back to the node that prompted the pivot — with a `rationale`
property. This is how context survives session boundaries and model changes.

**Low frequency is a feature.** Short holding periods (≤ 4h) reduce overnight exposure,
reduce execution slippage, and make regime sensitivity more visible.

---

## Quantitative Targets

Stored as a `ResearchTarget` node in the graph (target state — not yet implemented).
Defaulted values, rarely changed:

| Target | Value | Tier |
|---|---|---|
| Sharpe ratio | ≥ 2.0 | Professional |
| Sharpe ratio | ≥ 3.5 | Institutional |
| Max holding period | ≤ 4 hours | Both |
| Profit factor | ≥ 1.3 | Both |
| Calmar ratio | ≥ 1.5 | Both |
| Max drawdown | > -20% | Both |
| Minimum trades (absolute floor) | ≥ 30 | Both |
| Active-window frequency | ≥ 0.06 trades/day | Both |
| Correlation to all active Champions | < 0.30 | Target gate |

**Significance Gate — dual-hurdle:** Both the absolute floor (≥ 30 trades) AND the
activity hurdle (≥ 0.06 trades/day active-window frequency) must be satisfied for a Run
to be considered a Champion or Promotion Candidate. Either alone is insufficient.

**Active-Window Frequency:** `total_trades / (last_trade_timestamp − first_trade_timestamp)`
This uses the active window only — the period between first and last trade — preventing
frequency dilution from long flat regimes before or between trading activity.
A strategy that traded 30 times over 400 active days is measured on those 400 days,
not on 800 calendar days that included a flat regime gap.

**Duty Cycle (separate metric):** `active_days / total_backtest_days`
Tracks how often the strategy's target regime was present. A Duty Cycle of 0.5 means
the regime was active half the time. Used for portfolio heat and capacity reasoning —
not a promotion gate, but surfaced alongside frequency so the LLM can distinguish
a "Regime Specialist" (low duty cycle, high active-window frequency) from a
"Robust Performer" (high duty cycle, consistent frequency).

**What is NOT a target:** win rate, trend signal accuracy, directional bias. These are
byproducts of a good edge, not the edge itself. A strategy that wins 40% of trades at
a 3:1 R-multiple is preferable to one winning 60% at 1:1.

---

## [CURRENT] State

| Dimension | Current State |
|---|---|
| Research loop | Manual: backtest → `qw record --bundle` → `qw query` in a separate session |
| Idea tracking | None: no Hypothesis nodes; strategies exist but their origin is unknown |
| Context | Per-session, per-model: each session re-derives what was already known |
| Champion lifecycle | Binary: active Champion or RetiredChampion — no decay watch |
| Multi-model | Split-brain: ideation in one model, implementation in another |
| Redundancy check | None: no gate before suggesting a new strategy |
| Fragility | `fragility_report` (deprecated) — stale schema dependency |

The graph is a **linear data log**: Strategy → Trial → Champion. Accurate and queryable,
but with no root cause (Hypothesis), no pivot context (BRANCHED_FROM), and no decay
signal (FormerChampion).

---

## [TARGET] State

| Dimension | Target State |
|---|---|
| Research loop | Closed: Hypothesis logged → redundancy checked → Trial run → auto-ingested → Champion or FormerChampion |
| Idea tracking | Hypothesis nodes with `SUGGESTED` (source) and `BRANCHED_FROM` (pivot origin) |
| Context | Shared exocortex: same Neo4j graph accessible to any model via MCP tools |
| Champion lifecycle | Three-stage: Champion → FormerChampion (decay watch) → RetiredChampion (archive) |
| Multi-model | Any LLM with MCP access reads the same graph — no manual context bridging |
| Redundancy check | `check_redundancy` MCP skill runs before any strategy suggestion |
| Fragility | Distributed across `portfolio_alpha`, `former_champions`, `regime_performance` |

The graph becomes a **state-aware research exocortex**: a non-linear, provenance-rich tree
that reasons about its own past and guides the next direction.

---

## What This Is Not

- Not a trading system. Execution lives in `execution/oms.py`. The graph is the research index.
- Not a live signal feed. It records what was tested, what was promoted, and why.
- Not a VC product. Personal tool for one researcher — scale and multi-tenancy are not goals.
- Not an autonomous trading agent. Will approves all promotions and sets research direction.
  The AI navigates; the researcher decides.

---

## Reference Documents

- `docs/PROVENANCE_ENGINE.md` — authoritative graph schema and MCP tool reference
- `docs/RESEARCH_WORKFLOW.md` — how the research loop works in practice
- `docs/BACKLOG_ALIGNMENT.md` — which stories implement which target capabilities
- `docs/IS_RESEARCH_SOP.md` — 5-phase research methodology (Baseline → OOS Preparation)
