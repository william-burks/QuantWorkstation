Refine all draft stories in QuantWorkstation epic: $ARGUMENTS

Invoke skill: caveman

Two-agent flow: **qws-architect (Opus)** evaluates alignment + quality, **product-owner (Sonnet)** fixes and promotes.

---

## Phase 1 — Load context

Read before analysis:
1. `docs/MANIFESTO.md` — hard constraints, optimization targets
2. `docs/PROVENANCE_ENGINE.md` — schema. Split: **(a) current** (exists), **(b) target** (`[TARGET]`, not built)
3. `docs/RESEARCH_WORKFLOW.md` — research loop, interaction rules
4. `docs/BACKLOG_ALIGNMENT.md` — epic status, capability map, not-yet-implemented index
5. `qws_graph/epics/INDEX.md` — story list, dependencies
6. All story files in epic $ARGUMENTS folder (focus on `draft` status)

No draft stories → report empty, stop.

---

## Phase 2 — Strategic + structural evaluation (qws-architect, Opus)

Spawn qws-architect agent with all loaded context:
```
Before evaluating: read your memory at .claude/agent-memory/qws-architect/ — apply any
accumulated principles about story quality, schema patterns, and past refinement decisions.

Evaluate all draft stories in epic $ARGUMENTS for strategic alignment and implementation readiness.

**Authority rule:** BACKLOG_ALIGNMENT.md, PROVENANCE_ENGINE.md, MANIFESTO.md, and RESEARCH_WORKFLOW.md
are authoritative. If a story's scope doesn't match what the docs promise, the story is wrong — not the
docs. Never present "expand story OR update docs" options. Always expand the story. Stories with
outstanding design decisions cannot be promoted to ready.

Validation rules (hard fails → NEEDS WORK):
1. SCHEMA DRIFT: property/node/edge not in PROVENANCE_ENGINE.md
2. DEAD TOUCHPOINTS: file path in Repo Touchpoints doesn't exist and not annotated "— new"
3. VAGUE AC: any Acceptance Criteria not binary (true/false testable)
4. MANIFESTO BREACH: allows >4h holding or targets Sharpe < 2.0
5. SCOPE MISMATCH: story underdelivers what BACKLOG_ALIGNMENT.md promised — list missing deliverables

Strategic checks:
1. Do these stories collectively advance the research loop?
2. Any story that passes validation but drifts from target exocortex?
3. Schema changes consistent across stories in this epic?
4. Dependency chains complete — no implicit or circular deps?
5. Execution order optimal for capability unlock?
6. Scope creep — any story doing work that belongs in a later epic?

Output five sections:

**Epic Verdict**
PROCEED | WRONG EPIC | RESEQUENCE — is this epic still the right thing to build next given
current architecture, completed work, and backlog state? If not, say what should come first
and why. If WRONG EPIC → stop here, do not evaluate individual stories.

**Story Readiness**
| Story | ID | Readiness | Gap |
READY = ACs, touchpoints, scope, no blockers. NEEDS WORK = missing any. BLOCKED = upstream not CLOSED or depends on unbuilt [TARGET].

**Dependency Audit**
One line per: implicit dep, circular dep, missing from Not Yet Implemented index.

**Sequence Check**
Confirm or correct execution order. Flag reorder if it reduces risk or parallelizes work.

**Scope Flags**
One line per story with creep beyond original intent — what to cut or defer.

Keep to one screen. No narrative outside sections.
```

---

If architect verdict = WRONG EPIC → stop. Report what should come first. Do not proceed to Phase 3.
If architect verdict = RESEQUENCE → present reorder recommendation to user before proceeding.

## Phase 3 — Fix and promote (product-owner, Sonnet)

**Goal: every story exits this phase as READY or BLOCKED (on upstream dep). No DRAFT survivors.**

Spawn product-owner agent with architect's evaluation:
```
Apply the architect's findings to epic $ARGUMENTS draft stories.

For each NEEDS WORK story:
- Fix the specific gap identified (tighten ACs, correct touchpoints, fix schema refs, add missing deps)
- SCOPE MISMATCH: expand story to deliver everything BACKLOG_ALIGNMENT.md promised. Add missing
  deliverables to ACs, In Scope, and Repo Touchpoints. Never reduce the backlog promise.
- Re-validate against the 5 hard-fail rules after fixing
- After fixing: promote to READY. If you expanded scope, the expansion IS the fix — do not leave as draft.

For each BLOCKED story:
- Add explicit blocker to story's "Blocked On" field if missing
- Leave as BLOCKED with blocker noted (not draft)

For each READY story (no gaps, no blockers):
- Update status: draft → ready in story file, INDEX.md, BACKLOG_ALIGNMENT.md

Dependency fixes:
- Add implicit deps to story files and INDEX.md
- Update BACKLOG_ALIGNMENT.md dependency graph if chains changed

Sequence fixes:
- If architect recommended reorder, update INDEX.md execution order

Report: stories promoted, stories fixed, stories still blocked, remaining gaps.
```

## Phase 4 — Interview loop (remaining drafts)

If any stories are still draft after Phase 3 (PO couldn't resolve without input):

For each remaining draft:
1. PO presents the specific unresolved question to Will — not "A or B" options, but "I need to know X to finish this story"
2. Will answers
3. PO applies answer, completes the story, promotes to READY
4. Repeat until no drafts remain

**No story leaves refine-epic as draft.** End state is: all READY or all BLOCKED (with specific upstream dep).