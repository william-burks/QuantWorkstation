---
name: Spawn prompt / tool grant mismatch
description: Spawn prompts that ask an agent to run tools not in its tool grants — calls silently fail and orchestrator must recover
type: feedback
---

## Pattern
Spawn prompt instructs an agent to execute a command (Bash, git, make) that the agent's tool grants don't include.
The agent either silently skips the instruction, reports it can't execute, or hallucinates a result.
The orchestrator then has to manually re-run the check.

## Root cause category
Spawn prompt — instructions not matched to agent capabilities

## How to detect
- Agent returns "unable to verify" / "unknown" / "need git output" for items in the spawn prompt
- Orchestrator immediately re-runs the same check after the agent returns

## Fix template
1. Check the target agent's `tools:` field in its definition before writing a spawn prompt
2. If the agent lacks Bash: run shell checks in the orchestrator BEFORE spawning, then inject results as context:
   ```
   Context: <check name>: <result>
   ```
3. If the check is truly the agent's responsibility: add Bash to its tool grants (only if the agent is designed for execution, not analysis)

## Observed instances
- preflight.md Step 2 → product-analyst: asked to run `make -C qws_graph neo4j-status` and `git branch`. product-analyst has no Bash. 2 checks dropped, orchestrator had to recover. (2026-04-13)
