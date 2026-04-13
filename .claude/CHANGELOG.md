# Agent Workflow Changelog

Changes to agent commands, scripts, templates, and tooling.
Most recent first.

---

## 2026-04-12 — Tier 1/2/3 Workflow Standardization

### New scripts (`.claude/scripts/`)

| Script | Purpose |
|--------|---------|
| `locate-story.sh QWS-NNNN [--closed]` | Finds story file by content search. Replaces 4 different ad-hoc grep patterns across command files. |
| `set-story-status.sh QWS-NNNN STATUS [--closed]` | Updates status in story file, `INDEX.md`, and `BACKLOG_ALIGNMENT.md` atomically. `INDEX.md` and `BACKLOG_ALIGNMENT.md` blocked-on strikethrough still requires agent judgment. |
| `agent-init-state.sh <command>` | Clears guard trackers, builds `/tmp/symbol-index.txt` and `/tmp/schema-index.txt`, arms command sentinel. Replaces 7-line manual block in implement-story Step 0. |

### New Makefile targets

| Target | Usage | Does |
|--------|-------|------|
| `make commit-impl STORY= MSG=` | implement-story Step 6 | commit (agent stages first) |
| `make commit-test STORY=` | verify-story Step 9 | commit (agent stages first) |
| `make commit-push-qa EPIC=` | qa-epic Step 4 | commit + push to release branch |

### New docs/templates

| File | Purpose |
|------|---------|
| `docs/BASELINE_PROTOCOL.md` | Canonical definition of `make test-all` as the clean baseline. Per-agent usage table. |
| `.claude/templates/architect-evaluation.md` | Standard output format for qws-architect: required sections, verdict vocabulary, hard-block rules. Referenced by refine-epic, plan-sprint, define-feature. |

### Command file changes

**implement-story.md**
- Step 0: replaced 7-line manual setup block → `bash .claude/scripts/agent-init-state.sh implement-story`
- Step 1: replaced `grep -rl` → `STORY_FILE=$(.claude/scripts/locate-story.sh $ARGUMENTS)`
- Step 4: added SCOPE-LOCK hard constraint (was only in agent definition, not command file)
- Step 6: `git commit` → `make commit-impl STORY=$ARGUMENTS MSG="<summary>"`
- Step 8: `set-story-status.sh` now handles story file + INDEX.md + BACKLOG_ALIGNMENT.md in one call

**verify-story.md**
- Step 1: added `agent-init-state.sh verify-story` + `locate-story.sh` (was vague "Find story in epics/")
- Step 9: `git commit` → `make commit-test STORY=$ARGUMENTS`

**close-story.md**
- Step 1: `locate-story.sh` (was vague "Find story in epics/")
- Step 4: `set-story-status.sh $ARGUMENTS CLOSED` (was manual edit instruction)
- Step 6: trimmed — status already set in Step 4; only path update to `closed/` remains
- Step 7: trimmed — status already set in Step 4; only blocked-on strikethrough remains

**qa-epic.md**
- Steps 0 and 2f: `make test-unit` → `make test-all` (baseline consistency)
- Step 4: `git commit + git push` → `make commit-push-qa EPIC=$ARGUMENTS`

**run-epic.md**
- Step 3: `make test` → `make test-all`

**plan-sprint.md**
- Added SCHEMA DRIFT and TARGET REFERENCE hard-block rules (were only in refine-epic)
- Added architect output format reference to `.claude/templates/architect-evaluation.md`

**define-feature.md**
- Added SCHEMA DRIFT and TARGET REFERENCE hard-block rules (were only in refine-epic)
- Added architect output format reference to `.claude/templates/architect-evaluation.md`

**refine-epic.md**
- Added architect output format reference to `.claude/templates/architect-evaluation.md`

---

## 2026-04-12 — mypy clean baseline + make verify

- Fixed 863 mypy errors to 0 across 172 files (real type fixes + `# mypy: ignore-errors` on legacy/trial/test files)
- Added `make verify` (lint + typecheck + test-all), `make test-all`, `make test-integration` to Makefile
- Updated all agent command files, memory files, and open story ACs to use `make verify` instead of separate ruff/mypy invocations
- Baseline is now 0 mypy errors — any failure introduced by an agent is unambiguous