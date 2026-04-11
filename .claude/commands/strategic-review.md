Strategic review of QuantWorkstation direction and architecture: $ARGUMENTS

Invoke skill: caveman

Agent: qws-architect (Opus). Adversarial mode — argue against current assumptions.

Use when: between epics, when direction feels off, before major planning, or periodically as a health check.

## Setup
Read before reviewing:
1. Your memory at `.claude/agent-memory/qws-architect/` — prior reviews, accumulated principles
2. `docs/MANIFESTO.md` — mission, targets, hard constraints
3. `docs/PROVENANCE_ENGINE.md` — schema architecture
4. `docs/RESEARCH_WORKFLOW.md` — research loop, interaction model
5. `docs/BACKLOG_ALIGNMENT.md` — what's built, what's planned, what's next
6. `qws_graph/epics/INDEX.md` — completed and planned epics

If $ARGUMENTS provided, focus review on that area. Otherwise, full review.

## Part 1 — Vision challenge

Actively argue against the manifesto:
1. **Target still valid?** Sharpe >= 2.0, holding <= 4h, alpha focus — are these the right constraints given what research has shown? Any constraint that's blocking productive work?
2. **Optimization target:** is alpha still the right objective, or has the research revealed a different edge?
3. **Scope creep at the mission level:** has the exocortex vision expanded beyond what one person can maintain? Is the tool building outpacing the research it's supposed to serve?
4. **Missing capabilities:** what does the research workflow need that isn't in the manifesto or backlog?
5. **Dead weight:** any manifesto commitment that's no longer relevant?

## Part 2 — Architecture challenge

Stress-test the schema and system design:
1. **Over-engineering:** any nodes, edges, or tools that exist but don't serve a research outcome?
2. **Under-engineering:** any research patterns that require manual workarounds because the graph doesn't support them?
3. **Schema coherence:** do the node/edge relationships form a clean provenance chain, or are there orphan paths?
4. **Tool gaps:** any `qw` CLI commands or MCP tools that should exist but don't?
5. **Tool redundancy:** any tools that overlap or could be consolidated?
6. **Scaling assumptions:** will this architecture hold as the graph grows (100s of strategies, 1000s of runs)?

## Part 3 — Research workflow challenge

1. **Loop completeness:** can the full research cycle (hypothesize → test → evaluate → promote/abort) run without leaving the graph?
2. **Friction points:** where does the workflow require manual steps that break flow?
3. **Missing feedback loops:** does the system learn from its own failures (aborted strategies, failed OOS)?
4. **Data gaps:** any research data that's generated but not captured in the graph?

## Output

```
## Strategic Review

### Vision
| Area | Current | Challenge | Severity |
|------|---------|-----------|----------|
[rows — VALID, STALE, WRONG, or MISSING]

### Architecture
| Component | Challenge | Impact |
|-----------|-----------|--------|
[rows — SOUND, OVER-ENGINEERED, UNDER-ENGINEERED, or FRAGILE]

### Research workflow
| Step | Challenge | Friction |
|------|-----------|----------|
[rows — COMPLETE, GAP, or MANUAL]

### Proposed amendments
[numbered list — specific changes to MANIFESTO, PROVENANCE_ENGINE, or RESEARCH_WORKFLOW]
[each amendment: what to change, why, what it enables or unblocks]

### Verdict
ON TRACK | DRIFT DETECTED | PIVOT RECOMMENDED

### Priority
[if amendments proposed: which ones matter most and why]
```

After review: write key findings to `.claude/agent-memory/qws-architect/` as a dated strategic review.
Compare against prior reviews — flag recurring concerns or validated pivots.

**Important:** This skill proposes amendments. It does NOT modify docs. Will reviews and approves changes.
