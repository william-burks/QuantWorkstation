Refine all draft stories in QuantWorkstation epic: $ARGUMENTS

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

## Phase 1b — Template compliance gate

Before evaluating drafts, scan ALL story files in epic $ARGUMENTS regardless of status.

Required fields for every story:
- `## Type` — valid values: `code`, `schema`, `docs`, `research`, `infra`
- `## Acceptance Criteria`
- `## Definition of Done`

Additional required for `code`, `schema`, `infra` type stories:
- `## Repo Touchpoints`

For each story missing any required field:
1. Demote status to `draft` in the story file
2. Update status to `draft` in `INDEX.md`
3. Update status to `DRAFT` in `BACKLOG_ALIGNMENT.md`
4. Log: `QWS-XXXX demoted to DRAFT — missing: <field list>`

After demotion, continue to Phase 2 with the updated draft list.

No draft stories (including newly demoted) → report empty, stop.

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
6. TARGET REFERENCE: story ACs, Design, or presets reference nodes/edges/properties marked `[TARGET]` in
   PROVENANCE_ENGINE.md whose implementing story is not CLOSED. Scan ALL text in story file, not just
   Blocked On field. This includes cross-epic dependencies (e.g. referencing Epic 8 schema from Epic 6).
7. MISSING TYPE: no `## Type` field in story file → NEEDS WORK. Valid values: `code`, `schema`, `docs`, `research`, `infra`.
8. SCOPE TOO BROAD (code/schema stories only): Repo Touchpoints > 5 files → NEEDS WORK. Recommend specific split: which files belong in story A vs story B. Docs/research/infra stories are exempt from this rule.

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
- MISSING TYPE: add `## Type` field with the correct value (`code`, `schema`, `docs`, `research`, `infra`). Infer from story content — code changes → `code`, graph schema changes only → `schema`, written docs only → `docs`, research sessions → `research`, tooling/infra → `infra`. If ambiguous, use the primary deliverable.
- SCOPE TOO BROAD: split the story. Write two replacement story files with distinct IDs, each with ≤5 touchpoints. Update INDEX.md and BACKLOG_ALIGNMENT.md with the split. The original story ID is retired.
- SCOPE MISMATCH: expand story to deliver everything BACKLOG_ALIGNMENT.md promised. Add missing
  deliverables to ACs, In Scope, and Repo Touchpoints. Never reduce the backlog promise.
- TARGET REFERENCE: assess complexity of the unbuilt dependency.
  **Low complexity** (single property, small edge addition, trivial Cypher) → inline the fix
  into this story's scope. Add to In Scope and Repo Touchpoints. No card needed.
  **High complexity** (new node type, lifecycle system, multi-story dependency) → scope-cut.
  Remove from ACs/Design/presets, add "(deferred to QWS-XXXX)" annotation. Add a backlog
  candidate to BACKLOG_ALIGNMENT.md's Not Yet Implemented section: the cut capability, which
  story it was cut from, and which upstream story (QWS-XXXX) must close first.
  Both paths are autonomous — no interview needed.
- DEAD TOUCHPOINTS (non-existent CLI command or tool): replace with the documented equivalent
  from PROVENANCE_ENGINE.md or RESEARCH_WORKFLOW.md. If the docs describe how this capability
  works (e.g. promotion happens inside `qw record --bundle`), use that path. The story does
  not get to invent commands the docs don't promise. This is autonomous — not a design decision.
- Re-validate against the 6 hard-fail rules after fixing
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

## Phase 4 — Interview loop (design decisions only)

If any stories are still draft after Phase 3 — meaning the PO hit a genuine design decision
that cannot be resolved from docs alone (e.g. "new subcommand vs hook existing path",
"separate node type vs property on existing node"). Scope cuts and TARGET REFERENCE fixes
are NOT design decisions — those are handled autonomously in Phase 3.

For each remaining draft:
1. PO presents the design decision with architect-identified options and tradeoffs —
   not an open question, but "Option A: <specific>, Option B: <specific>, tradeoff: <what>"
2. Will picks
3. PO applies answer, completes the story, promotes to READY
4. Repeat until no drafts remain

**No story leaves refine-epic as draft.** End state is: all READY or all BLOCKED (with specific upstream dep).