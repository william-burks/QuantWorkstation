---
name: qa-engineer commit rule override
description: User task prompt "commit fixes, push" counts as explicit instruction — proceed without asking
type: feedback
---

qa-epic task prompts that say "commit fixes, push" are explicit commit permission. Do not stop to ask.

**Why:** CLAUDE.md hard rule 7 says no auto-commit without explicit instruction. The qa-epic task text "commit fixes, push" is that instruction.

**How to apply:** When running qa-epic, if user task says "commit fixes, push", stage only QA-fixed files and commit with `qa(epic-N): post-epic QA fixes — <summary>` message format.
