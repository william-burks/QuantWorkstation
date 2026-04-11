Sprint Planning session for QuantWorkstation.

Two-agent flow: **qws-architect (Opus)** evaluates, **product-owner (Sonnet)** writes.

---

## Phase 1 — Load context

Read before analysis:
1. `docs/BACKLOG_ALIGNMENT.md` — find **New Story Candidates** section (inputs)
2. `docs/MANIFESTO.md` — hard constraints (Sharpe >= 2.0, <= 4h holding, alpha focus)
3. `docs/PROVENANCE_ENGINE.md` — authoritative schema. Build two lists: **(a) current** (exists today), **(b) target** (marked `[TARGET]`, not yet built). Keep distinct.
4. `docs/RESEARCH_WORKFLOW.md` — research loop; every story must advance or support a step
5. `qws_graph/epics/INDEX.md` — existing epics, story IDs, status
6. README.md for each PLANNED epic — scope boundaries

**Housekeeping:** If any candidate in New Story Candidates was already shipped (marked "shipped inline" or has matching CLOSED story), remove it from the table. Clean before analyzing.

No candidates after cleanup → report empty, stop.

---

## Phase 2 — Strategic evaluation (qws-architect, Opus)

Spawn qws-architect agent with all loaded context:
```
Before evaluating: read your memory at .claude/agent-memory/qws-architect/ — apply any
accumulated principles about Will's sizing preferences, epic fit patterns, and schema decisions.

Evaluate these sprint candidates against the QuantWorkstation target state.

Candidates: [list from New Story Candidates]

For each candidate:
1. Epic fit — which existing epic absorbs it? Own epic only if operationally distinct.
2. Manifesto alignment — advances alpha, reduces friction, or enforces constraints? Flag if none.
3. Schema impact — new nodes/edges/properties? Conflict with PROVENANCE_ENGINE? Depends on [TARGET]?
4. Research loop position — which step does this advance?
5. Dependencies — specific story IDs that must be CLOSED first.
6. Execution order — where it slots within target epic.
7. Strategic verdict — does this move toward target exocortex or just ship a feature?

Also check:
- Any candidate that duplicates capability already CLOSED or in progress?
- Dependency chains circular or missing?
- Sprint sequence optimal for capability unlock?

Output: proposal table + verdicts + questions (only if answer materially changes what gets built).

For each candidate you verdict APPROVED (no MISALIGNED flag): write a principle-level memory
entry to .claude/agent-memory/qws-architect/ capturing what made it a good fit — epic alignment
rationale, research loop position, schema simplicity or complexity. Record the principle, not
the story ID. This builds institutional knowledge about what Will values in sprint candidates.
```

If architect reports MISALIGNED candidates → flag to user. Do not write stories for flagged candidates without user decision.

---

## Phase 3 — Write stories (product-owner, Sonnet)

**Only proceed if no open questions.** Questions → stop, wait for answers.

Spawn product-owner agent with architect's output:
```
Write story files for approved candidates. Architect evaluation attached.

Per story:
- Path: qws_graph/epics/<epic_folder>/story_N_<slug>.md
- Format: match existing stories — ID, Status, Blocked On, Summary, Problem, Goal, Design, In Scope, Out of Scope, Repo Touchpoints, Acceptance Criteria, Definition of Done
- Status: draft
- ACs must be specific and falsifiable. "Works correctly" is not an AC.
- DoD must include:
  - [ ] All affected README files updated
  - [ ] PROVENANCE_ENGINE.md updated if new nodes/edges/properties introduced

Filesystem check: for any existing file a story proposes to modify, confirm it exists. Phantom touchpoint → flag before writing.

After writing stories, update:
1. qws_graph/epics/INDEX.md — add stories with status + blocked-on
2. docs/BACKLOG_ALIGNMENT.md:
   - Add to Story → Capability Map under epic
   - Add new schema items to Not Yet Implemented with story ID
   - Remove promoted candidates from New Story Candidates
   - Update Dependency Graph if new chains added

Report: stories created, index entries, BACKLOG_ALIGNMENT updates.
```