You are running a Sprint Planning session for QuantWorkstation.

Invoke skill: caveman

## Phase 1 — Load Context

Read these files in order before doing any analysis:
1. `docs/BACKLOG_ALIGNMENT.md` — find the **New Story Candidates** section; these are your inputs
2. `docs/MANIFESTO.md` — hard constraints and optimization targets (Sharpe ≥ 2.0, ≤ 4h holding, alpha focus)
3. `docs/PROVENANCE_ENGINE.md` — authoritative graph schema; no story may invent nodes/edges/properties that conflict with it. **As you read, build two lists: (a) current — nodes/edges/properties/tools that exist today, and (b) target — items marked `[TARGET]`, which are planned but not yet built. Keep these distinct throughout your analysis.**
4. `docs/RESEARCH_WORKFLOW.md` — the research loop; every story must advance a step in this loop or explicitly support one
5. `qws_graph/epics/INDEX.md` — existing epics, story IDs used, current status

Also read the README.md for each existing PLANNED epic so you understand their scope boundaries.

If there are no candidates in the New Story Candidates section, report that and stop.

---

## Phase 2 — Analyze Each Candidate

For each candidate in the New Story Candidates table, determine:

1. **Epic fit** — which existing epic absorbs it, or does it warrant its own?
   - Use scope boundaries from each epic's README as the test
   - A candidate gets its own epic only if it is operationally distinct (e.g. a running process vs. a schema/CLI story) or crosses multiple existing epic concerns

2. **Manifesto alignment** — does this candidate advance alpha generation, reduce research friction, or enforce the hard constraints? If it does none of these, flag it.

3. **Schema impact** — does it introduce new nodes, edges, or properties? If yes, note which and confirm they don't conflict with PROVENANCE_ENGINE.md. If the story depends on a `[TARGET]` item (not yet built), flag that as a hard dependency — the target's implementing story must be CLOSED before this story can start.

4. **Filesystem reality** — for any existing file the story proposes to modify (not create), confirm it exists in the codebase. If the file doesn't exist and isn't marked as new, the story has a phantom touchpoint — flag it before writing.

4. **Dependencies** — what must be complete before this story can start? Be specific (story ID, not just "previous work").

5. **Execution order** — within its target epic, where does it slot? Before or after existing draft stories?

---

## Phase 3 — Produce the Plan

Output a proposal table:

| Candidate | Target Epic | Proposed ID | Exec Order | Blocked On | Flag |
|---|---|---|---|---|---|

Assign story IDs following the existing convention (next available number in the epic's sequence).

Below the table, list any **QUESTIONS** that must be answered before stories can be written. Number them. A question is required when:
- The candidate's scope is ambiguous enough that the story could go two meaningfully different directions
- Epic assignment is genuinely unclear between two options
- A schema decision is needed that PROVENANCE_ENGINE.md doesn't resolve

Do not ask about things you can decide from the documents. Prefer decisions over questions — only ask when the answer materially changes what gets built.

---

## Phase 4 — Write the Stories

**Only proceed to Phase 4 if there are no open questions.** If there are questions, stop after Phase 3 and wait for answers.

If all questions are resolved (either none exist, or the user has answered them), write each story file:

### Story file requirements

- Path: `qws_graph/epics/<epic_folder>/story_N_<slug>.md`
- Format: match existing story files exactly — ID, Status, Blocked On, Summary, Problem, Goal, Design (if non-trivial), In Scope, Out of Scope, Repo Touchpoints, Acceptance Criteria, Definition of Done
- Status: `draft`
- Thoroughness: Acceptance Criteria must be specific and testable. "Works correctly" is not an AC. Each criterion must be falsifiable.
- Every story's **Definition of Done** must include these two items in addition to implementation tasks:
  - `- [ ] All affected README files updated to reflect new capabilities`
  - `- [ ] PROVENANCE_ENGINE.md updated if any new nodes, edges, or properties were introduced`

### After writing story files, update:

1. `qws_graph/epics/INDEX.md` — add each new story to its epic's story list with correct status and blocked-on note
2. `docs/BACKLOG_ALIGNMENT.md`:
   - Add each story to the Story → Capability Map under its epic
   - Add any new nodes/edges/properties/tools to the Not Yet Implemented section with the story ID
   - Remove promoted candidates from New Story Candidates (or clear the section if empty)
   - Update the Dependency Graph if new dependency chains were added

Report what was written — story files created, index entries added, BACKLOG_ALIGNMENT sections updated.