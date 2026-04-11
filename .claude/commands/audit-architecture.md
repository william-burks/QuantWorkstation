Audit QuantWorkstation architecture alignment: $ARGUMENTS


Agent: qws-architect (Opus). Read-only. Health check — does what's built match what docs promise?

## Setup
Read before auditing:
1. Your memory at `.claude/agent-memory/qws-architect/` — check for prior audit findings
2. `docs/PROVENANCE_ENGINE.md` — authoritative schema
3. `docs/MANIFESTO.md` — hard constraints
4. `docs/RESEARCH_WORKFLOW.md` — research loop
5. `docs/BACKLOG_ALIGNMENT.md` — story status, capability map, not-yet-implemented
6. `qws_graph/epics/INDEX.md` — story list, statuses
7. `qws_graph/research/graph/cypher.py` — actual schema in code
8. `qws_graph/tests/fixtures/` — test fixtures
9. `.claude/CLAUDE.md` — sprint pointer

## Audit checks

### 1. Schema drift
Compare PROVENANCE_ENGINE.md against `cypher.py`:
- Nodes/edges/properties documented but missing from code
- Nodes/edges/properties in code but undocumented
- `[TARGET]` items that have CLOSED stories but aren't in code yet
- Properties with wrong types or missing constraints

### 2. Fixture consistency
Compare `qws_graph/tests/fixtures/` against PROVENANCE_ENGINE.md:
- Fixtures using stale schema (old properties, removed nodes)
- Missing fixtures for new nodes/edges
- Demo seed in cypher.py matches fixture expectations

### 3. Status consistency
Cross-reference INDEX.md, BACKLOG_ALIGNMENT.md, and story files:
- Story status mismatch between INDEX and story file
- CLOSED stories missing from capability map
- Not-yet-implemented items with CLOSED stories (should be removed)
- Blocked-on references pointing to CLOSED stories (blocker resolved, status stale)

### 4. Sprint pointer
Check `.claude/CLAUDE.md` sprint pointer:
- Does it reference the correct current epic?
- Are the "next" stories still valid (not CLOSED, not blocked)?

### 5. Capability regression
For each CLOSED story in the most recent epic:
- Do the repo touchpoints still exist?
- Were any files deleted or heavily refactored since close?
- Any `[TARGET]` items now built but still marked target?

### 6. Manifesto alignment
Spot check: do recent additions still honor hard constraints?
- Sharpe >= 2.0, holding <= 4h, alpha focus
- Interface is qw CLI + MCP only
- No FastAPI endpoints added

## Output

```
## Architecture Audit

### Schema drift
| Item | Doc says | Code says | Severity |
|------|----------|-----------|----------|
CLEAN or rows

### Fixture gaps
| Fixture | Issue |
|---------|-------|
CLEAN or rows

### Status inconsistencies
| Story | INDEX | Story file | BACKLOG |
|-------|-------|------------|---------|
CLEAN or rows

### Sprint pointer
CURRENT or STALE — what to update

### Capability regressions
| Story | Capability | Status |
|-------|-----------|--------|
CLEAN or rows

### Manifesto violations
CLEAN or specific violations

### Verdict
CLEAN | DRIFT DETECTED (N items)

### Recommended actions
[numbered list — what to fix, in priority order]
```

After audit: write findings summary to `.claude/agent-memory/qws-architect/` as a dated audit entry.
Compare against prior audits in memory — flag recurring drift patterns.
