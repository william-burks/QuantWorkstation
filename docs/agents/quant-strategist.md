# quant-strategist

**Model:** Opus 4.6 | **Role:** Novel alpha ideation from literature + first principles

On-demand hypothesis generator. Reads paper extracts and applies first-principles reasoning
to surface testable, theoretically grounded ideas. Only active after a confirmed OOS champion.

---

## Activation Gate

**Hard gate:** If no confirmed OOS champion exists, the agent outputs one line and stops:
```
No confirmed OOS champion yet. Strategist inactive.
```

There's nothing to diversify against without a baseline. Run sessions first.

**When available:** Navigator's session brief will show `Strategist Available: READY`

---

## Invocation

```
Use the quant-strategist agent.
[optional: current champion description + what's been tried]
```

If you don't provide context, strategist asks for it before proceeding:
```
What's the current champion strategy and its failure mode?
What instrument/timeframe are we focused on?
```

---

## What It Does

Generates 3–5 hypothesis seeds per session. Sources in priority order:

1. **Literature extracts** — reads `qws_researcher/data/extracts/*.md`, filters by instrument class and timeframe
2. **First principles** — market microstructure, behavioral finance, regime theory, cross-asset relationships
3. **WebSearch** — only when extracts don't cover a direction; arXiv q-fin and SSRN only

---

## Built-In Filter

Before surfacing any idea, applies:

- **Stationarity assumption** — is it reasonable for this asset/timeframe?
- **Decay mechanism** — crowding, arbitrage, regime change — what kills this signal?
- **Sample size** — what N does this need at the target holding period?
- **Transaction costs** — does it survive at the described frequency?

Only hypotheses that pass all four are surfaced. The failure condition is stated for each.

---

## Output Format (per idea)

```
## Idea N: [title]

**Mechanism:** [one sentence — why this signal should exist from first principles]
**Instrument:** [specific — e.g. "CL 1h futures"]
**Timeframe:** [holding period]
**Signal logic:** [concrete description — what to measure, when to enter/exit]
**Literature support:** [extract filename or "first principles only"]
**Key assumption:** [what must be true for this to work]
**Failure condition:** [what breaks it — specific]
**Correlation risk:** [low | medium | high vs described champions, with reason]
```

After all ideas:
```
Which of these to develop into a hypothesis? I'll write the idea file.
```

---

## Approving an Idea

```
Develop idea 2 into a hypothesis file.
```

Strategist writes `research/ideas/YYYY-MM-DD-<slug>.md`:

```yaml
---
status: raw
source: llm
related_hypothesis_id: ""
signal_type: [from idea]
instrument_class: [from idea]
timeframe: [from idea]
---

[mechanism sentence]

Signal: [logic]
Assumption: [key assumption]
Failure: [failure condition]
Literature: [extract filename or "first principles"]
```

This file surfaces in your next session brief under "Unprocessed Ideas."

---

## Boundaries

| Can | Cannot |
|---|---|
| Read any file | Run `qw record` |
| WebSearch (academic only) | Execute trials or modify strategies |
| Write to `research/ideas/` | Write anywhere else |
| — | `qw abort`, `qw champion`, `qw retire` |

---

## Common Mistakes

**Invoking before literature extraction:** Strategist reads `qws_researcher/data/extracts/`.
If you haven't run `batch_extract`, it has no literature to cite and will say so.
See [literature-pipeline.md](literature-pipeline.md).

**Invoking with no OOS champion:** The gate is hard. It stops immediately.
