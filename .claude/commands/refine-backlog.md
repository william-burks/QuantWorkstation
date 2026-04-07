You are running a Product Backlog Refinement (PBR) session for QuantWorkstation.

## Strict Validation Rules
1. SCHEMA DRIFT: Any property/node/edge not in PROVENANCE_ENGINE.md = NEEDS WORK.
2. DEAD TOUCHPOINTS: Any file path in Repo Touchpoints that does not exist AND is not annotated `— new` = NEEDS WORK.
3. VAGUE AC: Any Acceptance Criteria that isn't binary (True/False) = NEEDS WORK.
4. MANIFESTO BREACH: Any story allowing >4h holding periods or targeting Sharpe < 2.0 = NEEDS WORK.

Read the following files in order:
1. `docs/MANIFESTO.md` — mission, hard constraints, optimization targets
2. `docs/PROVENANCE_ENGINE.md` — authoritative graph schema and MCP tool contract
3. `docs/RESEARCH_WORKFLOW.md` — research loop, interaction rules, what good looks like
4. `docs/BACKLOG_ALIGNMENT.md` — epic status, capability map, not-yet-implemented index
5. `qws_graph/epics/INDEX.md` — canonical story list and dependencies

Then read every story file listed under the current epic (all `draft` stories in the active epic folder).

Use the first three documents as the reference standard. Every story should advance the research loop described in RESEARCH_WORKFLOW.md, respect the schema contract in PROVENANCE_ENGINE.md, and be consistent with the constraints and targets in MANIFESTO.md. Flag misalignment with these — not just internal inconsistency.

Produce a structured refinement report with four sections:

---

**Story Readiness**

For each draft story in the current epic, rate it: `READY` | `NEEDS WORK` | `BLOCKED`.

| Story | ID | Readiness | Gap |
|---|---|---|---|

Readiness criteria:
- `READY` = has Acceptance Criteria, Repo Touchpoints, clear In/Out of Scope, and no unresolved upstream blockers
- `NEEDS WORK` = missing one of the above, or scope is ambiguous
- `BLOCKED` = upstream story not yet complete

For every `NEEDS WORK` story, state the specific gap in one line.

---

**Dependency Audit**

List any dependency that is:
- Implicit (assumed but not written in the story's "Blocked On" field)
- Circular (A blocks B which blocks A)
- Missing from BACKLOG_ALIGNMENT.md's Not Yet Implemented index

One line per finding.

---

**Sequence Check**

Confirm or correct the execution order of unblocked stories. If a reorder would reduce integration risk or parallelize work, say so explicitly. Otherwise confirm the order is sound.

---

**Scope Flags**

For any story where the deliverable has grown beyond its original intent (gold-plating, implicit feature creep, or doing work that belongs in a later story), flag it with a one-line description of what to cut or defer.

---

Keep the report to one screen. No narrative outside the four sections. Flag problems — don't pad with praise.
