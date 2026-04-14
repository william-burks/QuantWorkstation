---
name: product-analyst audit profile
description: Recurring waste patterns, known issues, and validated fixes for the product-analyst agent
type: feedback
---

## Recurring issues
- **Missing file paths in spawn prompt**: 1 observed (preflight-13), root cause: orchestrator doesn't inject story paths before spawning, agent flails with 3+ Search calls. Status: open
- **Bash commands in spawn prompt**: 1 observed (preflight-13), root cause: product-analyst has no Bash tool; make/git instructions silently fail, orchestrator must recover manually. Status: open

## Opportunities
- 2026-04-13 | Inject story file paths into spawn prompt before product-analyst spawn (same pattern already used for qws-architect in preflight) | status: addressed
  - addressed: added Step 1b to preflight.md — resolves STORY_FILES before spawn, injects paths into prompt
- 2026-04-13 | Move infra checks (neo4j-status, git branch) to orchestrator, pass as context to product-analyst | status: addressed
  - addressed: Step 1b now runs make neo4j-status + git branch; results passed as "Infrastructure context" in spawn prompt

## Tool call frequency
| Tool | Total calls | Necessary | Wasted | Notes |
|------|-------------|-----------|--------|-------|
| Read | 2 | 2 | 0 | INDEX.md + BACKLOG_ALIGNMENT.md |
| Glob/Search | 4 | 1 | 3 | 3 flailing searches for story files |
| Bash | 0 | 0 | 0 | Not in tool grants |

## Common flows
| Flow | Frequency | Outcome | Notes |
|------|-----------|---------|-------|
| Read INDEX → Read BACKLOG → Search story files (3x) | 1x | wasted | no paths in prompt |
| Read INDEX → Read BACKLOG → immediate analysis | expected | necessary | what it should do with paths injected |

## Validated fixes
None yet.

## Known quirks
- product-analyst has `tools: Glob, Grep, Read` only — no Bash. Any spawn prompt with shell commands silently fails.
- Agent is correct to be Bash-free (read-only). Fix is always in the spawn prompt, not the definition.
- When story paths are missing, agent tries 3 search patterns before finding files (directory read attempt causes EISDIR error).
