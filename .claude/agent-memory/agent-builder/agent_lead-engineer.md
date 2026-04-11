---
name: Lead-engineer audit history
description: Efficiency metrics, waste patterns, and applied fixes for the lead-engineer agent across story runs
type: project
---

## Efficiency Table

| Run | Story | Total | Necessary | Wasted | Waste% | Top Pattern | Fixes Applied |
|-----|-------|-------|-----------|--------|--------|-------------|---------------|
| 20260411T200900 | QWS-0801 | 144 | 87 | 57 | 40% | file-reread | baseline |
| 20260411T200900-retry | QWS-0801 | 228 | 111 | 117 | 51% | lint-loop | prose prohibition (FAILED) |
| 20260411T215414 | QWS-0801 | 166 | 86 | 80 | 48% | scope-archaeology | structural lint fix (lint-loop eliminated) |
| 20260411T223754 | QWS-0801 | 152 | 67 | 85 | 56% | doc-overreach | read-guard + discovery gate + STOP gate |
| 20260411T231923 | QWS-0801 | 148 | 86 | 62 | 42% | file-reread | spawn-split + grep/search guards |

## Confirmed Waste Patterns

### 1. lint-loop — ELIMINATED
Prose prohibition failed. Structural fix (agent-guard.sh + Makefile split) worked: zero ruff attempts in Run 3.

### 2. scope-archaeology (42 calls in Run 3, #124-166)
After completing Step 9, agent read `verify-story.md`, edited `data_dictionary.yaml`, `graph_v1_contract.md`,
`PROVENANCE_ENGINE.md` (5 edits), then read `close-story.md` and executed full close lifecycle.
Step 9 says "Do not mark CLOSED" — agent read it and ran close-story anyway. Prose prohibition failed.

**Fix applied (structural):**
- `implement-story.md` Step 9: Hard STOP gate with explicit forbidden-file list
- `lead-engineer.md`: Read hook added (`agent-read-guard.sh`)
- `agent-read-guard.sh`: blocks Read of `verify-story.md` and `close-story.md`

### 3. discovery-bleed (14 calls in Run 3, #14-32)
After MCP returned target locations, agent continued broad grepping — class scans, NeoConnector searches,
CLI function inventories. Should have pivoted to reading + editing after MCP hit.

**Fix applied:**
- `implement-story.md` Step 3: Phase gate + explicit discovery budget (max 2 search_code + 1 Grep per file)
- `project_tooling.md`: Discovery budget recipe added to agent memory

### 4. file-reread (28 calls in Run 3; 44 in Run 5 — store.py×7, query.py×9, cypher.py×6, cli.py×5, graph_v1_contract.md×7)
Files already in context re-read before editing. Prose failed every run. Hook not firing (agent frontmatter hooks don't fire for spawned subagents — confirmed by chmod test passing but re-reads still occurring in trace).

**Root cause confirmed (Run 5):** `hooks:` in agent YAML frontmatter applies only to main-session tool calls, not subagent tool calls. All three guard hooks (Read, Grep, search_code) were silently ignored.

**Fix applied (structural — Run 5→6):**
- Moved Read/Grep/search_code hooks to `.claude/settings.json` (global, fires for all agents)
- Bash hook stays in lead-engineer.md only (ruff already blocked by deny list)
- `implement-story.md` Step 3: large file offset hints table (store/cli/cypher/query)
- `implement-story.md` Step 3 STOP: added graph_v1_contract.md to no-reread list
- `implement-story.md` Step 9: PROVENANCE_ENGINE prohibition now conditional on story DoD scope
- `verify-story.md` Step 7b: re-run acceptance tests instead of just checking checkboxes

## Principle Confirmed
**Prose prohibition failure rate ~100% when prohibited action is agent's default instinct.**
Confirmed across qa-engineer (8+ runs) and lead-engineer (3 runs).
Only structural enforcement works: hooks, guards, removing the tool/command.

## Applied Fix Inventory
| Fix | File | Status |
|-----|------|--------|
| Makefile split (typecheck/lint) | Makefile | Applied Run 2→3 — eliminated lint-loop |
| agent-guard.sh lint block | .claude/scripts/agent-guard.sh | Applied Run 2→3 — confirmed working |
| implement-story Step 9 STOP gate | .claude/commands/implement-story.md | Applied Run 3→4 |
| agent-read-guard.sh (scope + re-read) | .claude/scripts/agent-read-guard.sh | Applied Run 3→4 |
| Read hook in lead-engineer.md | .claude/agents/lead-engineer.md | Applied Run 3→4 |
| Discovery phase gate + budget | .claude/commands/implement-story.md | Applied Run 3→4 |
| Discovery budget in agent memory | .claude/agent-memory/lead-engineer/project_tooling.md | Applied Run 3→4 |
| Spawn-split: Spawn A (impl+verify), Spawn B (close) | .claude/commands/run-epic.md | Applied Run 4→5 |
| Step 9 STOP gate — remove verify-story block | .claude/commands/implement-story.md | Applied Run 4→5 |
| agent-read-guard.sh — remove verify-story block | .claude/scripts/agent-read-guard.sh | Applied Run 4→5 |
| agent-discovery-guard.sh (search_code cap=10) | .claude/scripts/agent-discovery-guard.sh | Applied Run 4→5 |
| agent-grep-guard.sh (block Grep on Read files) | .claude/scripts/agent-grep-guard.sh | Applied Run 4→5 |
| Grep + search_code hooks in lead-engineer.md | .claude/agents/lead-engineer.md | Applied Run 4→5 |
| Discovery tracker reset in Step 0 | .claude/commands/implement-story.md | Applied Run 4→5 |
| Hooks moved to settings.json (Read/Grep/search_code) | .claude/settings.json | Applied Run 5→6 — fixes frontmatter-hook firing bug |
| Large file offset hints table in Step 3 | .claude/commands/implement-story.md | Applied Run 5→6 |
| graph_v1_contract.md added to no-reread STOP list | .claude/commands/implement-story.md | Applied Run 5→6 |
| PROVENANCE_ENGINE prohibition conditional on DoD scope | .claude/commands/implement-story.md | Applied Run 5→6 |
| verify-story Step 7b: AT re-run (was no-op checkbox check) | .claude/commands/verify-story.md | Applied Run 5→6 |
