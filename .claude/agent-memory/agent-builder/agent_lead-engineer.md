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

### 4. file-reread (28 calls in Run 3 — cli.py×5, query.py×5, cypher.py×5, store.py×2)
Files already in context re-read before editing. Prose failed 3 consecutive runs.

**Fix applied (structural):**
- `agent-read-guard.sh`: re-read counter — blocks 3rd+ read of same source file
- `lead-engineer.md`: stronger prose callout with specific file names + "hook-enforced" label
- `implement-story.md` Step 0: tracker dir cleanup (`rm -rf /tmp/agent-read-tracker`)

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
