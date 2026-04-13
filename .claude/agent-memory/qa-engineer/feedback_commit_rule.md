---
name: qa-engineer commit rule override
description: Commit permission in qa-epic applies ONLY to fixture/seed fixes at Step 4, never to lint auto-fixes
type: feedback
---

Commit permission in qa-epic is narrowly scoped to **fixture/seed fixes made in Step 3**, committed via `make commit-push-qa` at Step 4. It does not extend to lint auto-fixes applied by `make lint`.

**Why:** `make lint` runs `ruff check . --fix && ruff format` which auto-applies changes to source files. Committing those changes is not authorized — the qa-engineer command file explicitly says "Do NOT fix lint errors." The orchestrator spawn prompt saying "Commit only fixture/seed fixes" means exactly that: only files you edited in Step 3.

**How to apply:**
- At Step 4: only `git add` files explicitly edited during Step 3 fixture/seed fixes. Never `git add -A` or stage files modified by `make lint`.
- If `make lint` auto-fixed anything: do NOT commit those changes. Write a fixlist instead (Step 2c Phase 3). Lint-mechanic handles the commit.
- Raw `git commit` and `git push` are never allowed — use `make commit-push-qa EPIC=$ARGUMENTS` only.
- If Step 3 made no changes: skip Step 4 commit entirely.
