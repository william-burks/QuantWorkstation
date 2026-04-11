---
name: lint-mechanic audit history
description: Efficiency audit history for the lint-mechanic agent across QA runs
type: project
---

# lint-mechanic audit history

## Run 20260411T165551 — Epic 6
- 7 calls, 4 necessary, 3 wasted (43% waste)
- Verdict: completed (1 file, 1 error fixed, pushed)
- Top waste pattern: **lint-rerun**

### Root cause
Agent ran `make lint 2>&1 | tail -5` (correct), but `tail -5` didn't surface the ruff summary — mypy output pushed it past the window. Agent re-ran `make lint | grep` then `make lint | tee | tail -20` to get a bigger window. Three `make lint` runs when the hard limit is 2.

### Fix applied (2026-04-11)
Process step 4 changed to `make lint 2>&1 | tee /tmp/lint_mechanic_verify.txt | tail -20`. Fallback: `grep "Found" /tmp/lint_mechanic_verify.txt` on the tee'd file — no second `make lint` needed. Hard limit reinforced in Rules: "Never `make lint | grep` — use the tee'd file instead."

## Run 20260411T180719 — Epic 6
- 11 calls, 5 necessary, 6 wasted (55% waste)
- Verdict: completed (1 file, 1 error fixed, pushed)
- Top waste pattern: **pre-fix-scoping** (4 calls) + **grep-piped-lint** (2 calls)

### Root cause
Agent ran `make lint` 4x BEFORE applying edit (calls 3-6) to "understand" the I001 error, despite fixlist containing full description. Then 2 more `make lint | grep` calls post-fix (calls 8-9) despite grep-pipe ban. Total 6 lint runs — hard limit is 2.

Two failures:
1. "Do NOT run make lint until ALL fixes applied" was read as sequencing advice, not pre-fix ban. Haiku needs explicit phase gates, not prose prohibitions.
2. `grep` pipe ban only appeared in Rules bullet; agent in "scoping mode" didn't consider post-fix rules to apply yet.

### Fix applied (2026-04-11)
1. Rules section: added explicit "ZERO make lint before editing" + "fixlist IS your diagnosis" + "any lint before Step 4 is a bug"
2. Process section: split into Phase A (fix — no lint) and Phase B (verify — lint allowed here only)
3. Spawn prompt (run-epic.md): added "fixlist is your complete diagnosis. Do NOT run make lint before fixing. Phase A requires zero lint runs."
4. Reinforced grep-pipe ban with bold: "Never pipe lint through grep"

## Efficiency trend
| Run ID | Total | Necessary | Wasted | Waste% | Top pattern |
|--------|-------|-----------|--------|--------|-------------|
| 20260411T163612 | 6 | 4 | 2 | 33% | lint-rerun |
| 20260411T165551 | 7 | 4 | 3 | 43% | lint-rerun |
| 20260411T180719 | 11 | 5 | 6 | 55% | pre-fix-scoping |
