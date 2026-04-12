# Story 1 — Research Ideas Layer

## ID
QWS-0901

## Status
DRAFT

## Blocked On
None

## Summary
Create `research/ideas/` as a pre-graph holding area for half-formed observations. Add a
"Pre-Graph Ideation" section to `docs/RESEARCH_WORKFLOW.md` documenting file convention and
promotion trigger. Add one example idea file. No graph changes, no CLI changes.

## Problem
Observations and market intuitions are lost between sessions because there is no designated
place to park them before they are testable. Ideas that do not yet qualify for a Hypothesis
node either get forgotten or force premature hypothesis logging. The graph should be the
permanent record, but it needs a staging area for raw material.

## Goal

```zsh
# Will parks an observation mid-session
echo "CL often reverses within 30min of 10:30am EIA print — low vol environment" \
  > research/ideas/2026-04-11-cl-eia-reversal.md

# Later: promotes to hypothesis
qw record --hypothesis "CL mean-reversion post-EIA in low vol" --source user
# Then update related_hypothesis_id in the idea file
```

## Schema
No graph changes. File-only convention.

Idea file frontmatter:
```yaml
---
status: raw           # raw | hypothesis_logged | rejected
source: user          # user | llm | pivot
related_hypothesis_id: ""   # populated after qw record --hypothesis
---
```

## In Scope
- `research/ideas/` directory (`.gitkeep` to track in git)
- `docs/RESEARCH_WORKFLOW.md` — new "Pre-Graph Ideation" section:
  - Purpose: staging area for observations before they are testable
  - File convention: `YYYY-MM-DD-<slug>.md`
  - Frontmatter spec: `status`, `source`, `related_hypothesis_id`
  - Promotion trigger: Will or navigator decides → `qw record --hypothesis` → update
    `related_hypothesis_id` in idea file → set `status: hypothesis_logged`
  - Rejection: set `status: rejected` with a one-line reason in the file body
- `research/ideas/2026-04-11-example-cl-eia-reversal.md` — illustrative example idea file

## Out of Scope
- Any CLI changes to `qw`
- Any graph node or edge changes
- Automated scanning or promotion tooling (that is QWS-0904 scope)

## Repo Touchpoints
- `research/ideas/.gitkeep` (new)
- `research/ideas/2026-04-11-example-cl-eia-reversal.md` (new)
- `docs/RESEARCH_WORKFLOW.md`

## Acceptance Criteria
- [ ] `research/ideas/` directory exists and is tracked in git via `.gitkeep`
- [ ] `docs/RESEARCH_WORKFLOW.md` contains "Pre-Graph Ideation" section with file convention,
  frontmatter spec, and promotion trigger documented
- [ ] Example idea file exists at `research/ideas/2026-04-11-example-cl-eia-reversal.md` with
  correct frontmatter (`status: raw`, `source: user`, `related_hypothesis_id: ""`)
- [ ] No graph schema changes, no CLI changes

## Definition of Done
- [ ] `research/ideas/.gitkeep` committed
- [ ] Example idea file present with valid frontmatter
- [ ] RESEARCH_WORKFLOW.md Pre-Graph Ideation section merged
- [ ] All tests pass (`ruff check .` and `mypy --strict .` clean)
- [ ] Story marked CLOSED
