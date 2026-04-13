Define a QuantWorkstation feature: $ARGUMENTS

Two-agent flow: **qws-architect (Opus)** reasons, **product-owner (Sonnet)** writes candidate entry.

---

## Phase 1 — Feature analysis (qws-architect, Opus)

Spawn qws-architect agent:
```
Before analyzing: read your memory at .claude/agent-memory/qws-architect/ — apply any
accumulated principles about feature fit, schema patterns, and past rejections.

Load: docs/MANIFESTO.md, docs/PROVENANCE_ENGINE.md, docs/RESEARCH_WORKFLOW.md,
      docs/BACKLOG_ALIGNMENT.md, qws_graph/epics/INDEX.md

Analyze feature: $ARGUMENTS

Hard-block rules (override all other verdicts — see `.claude/templates/architect-evaluation.md`):
1. SCHEMA DRIFT: property/node/edge not in PROVENANCE_ENGINE.md current section → flag in Schema Impact, verdict = NEEDS_WORK
2. TARGET REFERENCE: AC or Design references `[TARGET]` node/edge whose implementing story is not CLOSED → verdict = BLOCKED

Answer:
1. Already covered? Check CLOSED stories and current capabilities — if yes, say so and stop.
2. Which epic absorbs this? Own epic only if operationally distinct.
3. Advances which research loop step?
4. Manifesto alignment: alpha, friction reduction, or hard constraint?
5. Schema impact: new nodes/edges/properties? Conflict with PROVENANCE_ENGINE? Depends on [TARGET]?
6. How many stories? Could be one or several — size correctly.
7. Execution order and dependencies — what must be CLOSED first?

Output format: follow `.claude/templates/architect-evaluation.md`.
Required sections: Overall Verdict, Per-Item Assessment, Schema Impact, Open Questions.
Additional sections for this command: Fit (table), Story Breakdown.

Overall Verdict tokens for this command: `READY TO WRITE` | `NEEDS DECISION` | `NOT WORTH BUILDING`

If verdict = READY TO WRITE: write a principle-level memory entry to
.claude/agent-memory/qws-architect/ capturing what made this feature a good fit —
which manifesto pillar it advances, why it belongs in this epic, what schema decisions
were made and why. Record the principle, not the feature name.
If verdict = NOT WORTH BUILDING: write a memory entry capturing why — what constraint
it violated or what capability it duplicated. Prevents similar proposals surfacing again.
```

If NEEDS DECISION → stop, present to user. Do not proceed to Phase 2.
If NOT WORTH BUILDING → stop, explain why.

---

## Phase 2 — Add to candidates (product-owner, Sonnet)

Only if architect verdict = READY TO WRITE and user approves.

Spawn product-owner agent with architect's output:
```
Add the following candidate(s) to the New Story Candidates table in docs/BACKLOG_ALIGNMENT.md:

| Candidate | What it delivers |
[one row per story from the architect's breakdown]

Append to the existing table. Do not remove existing rows.
```