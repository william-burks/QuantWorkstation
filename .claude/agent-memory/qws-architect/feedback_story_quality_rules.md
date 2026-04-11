---
name: Story quality validation rules
description: Hard validation rules for QWS story drafts — schema drift, dead touchpoints, vague AC, manifesto breach
type: feedback
---

Every story draft must pass four hard-fail checks before READY:
1. SCHEMA DRIFT: every node/edge/property must exist in PROVENANCE_ENGINE.md [CURRENT] or be the deliverable of THIS story
2. DEAD TOUCHPOINTS: every file path in Repo Touchpoints must exist or be annotated "-- new"
3. VAGUE AC: every acceptance criterion must be binary (true/false testable)
4. MANIFESTO BREACH: no design allows >4h holding or targets Sharpe < 2.0

**Why:** First evaluation (2026-04-10) found QWS-0601 delivering entirely different schema than BACKLOG specified, missing touchpoint sections, and forward dependencies between stories. These checks catch misalignment early.

**How to apply:** Run these four checks on every story evaluation. Also check: does the draft match what BACKLOG_ALIGNMENT says it should deliver? Scope mismatch between story and backlog is a separate failure mode from the four above.
