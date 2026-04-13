# Architect Evaluation — Standard Output Format

All qws-architect evaluations MUST use these exact section names and verdict tokens.
Referenced by: refine-epic.md, plan-sprint.md, define-feature.md.

---

## Required sections (every evaluation)

### Overall Verdict
One token on its own line:
`PROCEED` | `RESEQUENCE` | `WRONG_EPIC` | `NEEDS_DECISION` | `NOT_WORTH_BUILDING`

If anything other than `PROCEED`: one sentence explaining what must change or happen first.

### Per-Item Assessment
| Item | ID | Verdict | Gap |
|------|----|---------|-----|

Per-item verdict tokens:
- `APPROVED` — ready, no gaps
- `NEEDS_WORK` — specific gap identified, fixable by product-owner
- `BLOCKED` — upstream story not CLOSED or depends on unbuilt `[TARGET]`
- `REJECTED` — manifesto breach or not worth building; one-line reason required

### Schema Impact
`NONE` — or list each addition:
- Node: `NodeLabel` — properties: `prop1`, `prop2`
- Edge: `(A)-[:REL_TYPE]->(B)` — properties: `prop1`

Conflict with PROVENANCE_ENGINE current section: `YES (detail)` | `NO`

### Open Questions
`NONE` — or numbered list. Only questions that materially change what gets built.
Prefer a decision over a question wherever possible.

---

## Hard-block rules (apply to every evaluation — override all other verdicts)

1. **SCHEMA DRIFT** — property, node, or edge not in PROVENANCE_ENGINE.md current section
   → item verdict = `NEEDS_WORK`. Gap = "schema not in PROVENANCE_ENGINE: <name>"
2. **TARGET REFERENCE** — AC, Design, or preset references a `[TARGET]` node/edge/property
   whose implementing story is NOT CLOSED
   → item verdict = `BLOCKED`. Gap = "depends on unbuilt [TARGET]: <name> (implementing story: QWS-XXXX)"

These rules are non-negotiable. Do not present "add to story OR update docs" options for SCHEMA DRIFT.
The story is wrong; the docs are authoritative.

---

## Additional sections (command-specific, append after required sections)

Each command may define its own additional sections. Standard extras:

**Dependency Audit** — implicit deps, circular deps, missing entries in Not Yet Implemented index.
**Sequence Check** — confirm or correct execution order.
**Scope Flags** — stories with creep beyond original intent.
**Story Breakdown** — per-feature story count and AC sketch.
**Fit** — epic placement, research loop step, manifesto pillar.

---

## Format rules

- No narrative outside sections.
- Keep to one screen total.
- Tables over prose for per-item data.