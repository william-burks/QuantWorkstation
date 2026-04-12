# RESEARCH WORKFLOW — Playbook

> **LLM INSTRUCTION BLOCK**
> ```
> ROLE: You are the Navigator. Will is the Guiding Researcher.
>
> BEFORE suggesting a strategy: query the graph (recent_champions, former_champions).
> AFTER a research session: produce a summary report — do not narrate execution step-by-step.
> WHEN proposing a new direction: create a BRANCHED_FROM edge with explicit rationale.
>   This is non-optional — it is how context survives session boundaries.
> DO NOT attempt to promote a Champion or retire a FormerChampion without Will's approval.
> DO NOT reference node types or MCP tools marked [TARGET] in PROVENANCE_ENGINE.md until
>   their stories are COMPLETE in BACKLOG_ALIGNMENT.md.
> ```

---

## Pre-Graph Ideation

`research/ideas/` is the staging area for observations that are not yet testable as a
Hypothesis. Park half-formed intuitions here before they qualify for `qw record --hypothesis`.

### File Convention
Filename: `YYYY-MM-DD-<slug>.md`
Example: `research/ideas/2026-04-11-cl-eia-reversal.md`

### Frontmatter Spec
```yaml
---
status: raw           # raw | hypothesis_logged | rejected
source: user          # user | llm | pivot
related_hypothesis_id: ""   # populate after qw record --hypothesis
---
```

### Lifecycle
1. **Park** — create file with `status: raw` when an observation surfaces mid-session
2. **Promote** — Will or navigator decides it is testable →
   `qw record --hypothesis "<text>" --source user` → copy returned hypothesis ID into
   `related_hypothesis_id` → set `status: hypothesis_logged`
3. **Reject** — idea is superseded or dead end → set `status: rejected`, add one-line reason
   in file body. File is preserved (not deleted) for audit trail.

### What belongs here vs. the graph
| Here (`research/ideas/`) | Graph (Hypothesis node) |
|---|---|
| Half-formed observation | Testable, specific hypothesis with instrument + timeframe |
| "CL often reverses post-EIA in low vol" | "CL 1h mean-reversion within 30min of 10:30am EIA in ATR < 0.5 regime" |
| Not yet checked for redundancy | Redundancy check run before logging |

---

## [CURRENT] The Manual Loop

The current workflow is functional but fragmented. Each step requires manual handoff.

```
1. Will identifies a research direction (ad-hoc, no Hypothesis node)
        ↓
2. Trial script runs (research/trials/ or research/bin/ shell runner)
        ↓
3. Results written to research/results/futures/<strategy>/runs/<timestamp>/
        ↓
4. qw record --bundle <dir>   ← graph ingestion (soft-fail: qw record ... || true)
        ↓
5. Will queries results manually in a new session:
     qw query --name recent_champions
     qw query --name run_history --param strategy_id=<id>
        ↓
6. Ideas for next direction generated in a separate LLM session
   with no access to graph state
```

**What gets lost at every step:**
- Why this direction was chosen (no Hypothesis node)
- What was tried before (no redundancy check)
- What failed OOS and why (no FormerChampion query)
- The rationale for any pivot (no BRANCHED_FROM edge)

---

## [CURRENT] The Split-Brain Problem

| Session | Model | What it knows |
|---|---|---|
| Brainstorming | Gemini / Claude | Ideas, market intuition — no graph access |
| Implementation | Claude Code | Code structure — no research history |
| Review | Any | Has to re-derive context from scratch |

There is no shared memory. Will is the only bridge between sessions.
Every context-heavy question ("what have we tried on CL?") requires manual retrieval
and re-paste. This is the core inefficiency the exocortex eliminates.

---

## [TARGET] The Unified MCP Loop

Any model with MCP access reads from the same Neo4j graph. Context is not per-session —
it is persistent and queryable.

```
1. LLM or Will logs a Hypothesis
     MCP: log_hypothesis(text, source)
     Graph: (Hypothesis)-[SUGGESTED]->(LLM/User)
        ↓
2. Redundancy check before any trial is proposed
     MCP: check_redundancy(hypothesis_id)
     Checks: active Champions, FormerChampions (cause-of-death), SEMANTICALLY_RELATED Hypotheses
     MCP: list_aborted → check if proposed logic matches an aborted Strategy
     If aborted match found → intervene: "This logic was aborted on [date] due to [reason].
       Do you have a new hypothesis that addresses that flaw?"
     If match found elsewhere → flag explicitly before proceeding
        ↓
3. If novel: LLM generates Strategy code
     If pivot: BRANCHED_FROM edge created linking new Hypothesis to source node + rationale
        ↓
4. Trial runs (unchanged — shell runners, soft-fail ingest)
     qw record --bundle <dir> || true
     Graph: (Strategy)-[HAS_TRIAL]->(Trial) auto-linked to Hypothesis via TESTED_AS
        ↓
5. Promotion gate (target — correlation-gated)
     IF sharpe >= 2.0
        AND total_trades >= 30
        AND active_window_frequency >= 0.06
        AND evidence_score > current_champion
        AND corr_to_all_champions < 0.30
     THEN auto-promote candidate surfaced → Will approves
        ↓
6. Post-run summary report (not step-by-step narration)
     LLM produces: top candidates, regime context, fragility flags, suggested next pivot
```

---

## Researcher Role — Will (Guiding Researcher)

| Decision | Will | AI |
|---|---|---|
| Champion promotion approval | ✓ | Surfaces candidate, explains evidence |
| Research direction | ✓ | Proposes options with graph-backed reasoning |
| Pivot rationale | ✓ (approves) | Writes BRANCHED_FROM edge |
| Regime interpretation | ✓ | Surfaces regime_performance data |
| FormerChampion retirement | ✓ | Flags decay threshold breach |
| Trial execution | ✓ | Never initiates a backtest autonomously |

The AI does not make trading decisions. It navigates the graph, surfaces evidence,
and flags when constraints are violated.

---

## Interaction Modes

### Interactive (during active research session)
- Real-time guidance as Will explores results
- Answer questions about graph state: "what's the best CL trial this quarter?"
- Flag constraint violations before Will invests time in a direction

### Summarized (post-run)
- Triggered after all shell runners complete
- Produces a structured digest:
  - New Trials ingested and their tier/evidence_score
  - Promotion candidates (dual-hurdle passed)
  - Champions with OOS deviation (IS/OOS drift flag)
  - Suggested next pivot with BRANCHED_FROM rationale
- Does NOT narrate execution steps — Will can read the receipt

---

## Pivot Point Tracking

A pivot is any moment where a research direction changes based on an existing result.
Without a record, the next session cannot know why the new direction exists.

**When to create a BRANCHED_FROM edge:**
- A Trial had good Sharpe but failed the drawdown gate → pivot to tighter stops
- A Champion degraded to FormerChampion → pivot to a new regime hypothesis
- A correlation check shows redundancy with an active Champion → pivot instrument or logic

**What goes in `rationale`:**
Be specific. Not "didn't work" but "CL-1h-bear Trial 63bcef04 hit -18% DD during CPI vol spike —
pivoting to ATR-scaled stop to handle event risk."

The rationale is the most durable piece of context in the system. It survives model changes,
session resets, and time gaps.

---

## [TARGET] Multi-Model Exocortex

The goal is not Claude-specific or Gemini-specific. Any model that can call MCP tools
participates in the same research memory.

```
Model A (brainstorming)  ──┐
Model B (implementation) ──┼──► Neo4j Graph (shared exocortex) ◄──► qw CLI
Model C (review)         ──┘
```

No model has privileged access. No model needs to be "caught up." The graph is the
single source of truth — sessions are stateless, the graph is stateful.

---

## Reference Documents

- `docs/MANIFESTO.md` — mission, quantitative targets, philosophy
- `docs/PROVENANCE_ENGINE.md` — graph schema, MCP tools, promotion gate logic
- `docs/BACKLOG_ALIGNMENT.md` — what is built vs. what is planned
- `docs/IS_RESEARCH_SOP.md` — 5-phase research methodology (Baseline → OOS Preparation)
