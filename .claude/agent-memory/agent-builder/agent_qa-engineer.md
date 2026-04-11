# qa-engineer audit history

## Run 20260411T174215 — Epic 6
- 45 calls, 27 necessary, 18 wasted (40% waste)
- Verdict: CLEAN
- Top waste patterns: **file-reread** (lint.txt 10×, N-read loop), PROVENANCE_ENGINE grep (2), cypher.py re-read+grep (2), fixture scan (1), post-STOP grep (2)

### Root cause
Phase 2 arrows.txt had file paths only — no error codes. Agent forced back to lint.txt once per in-scope file (10 reads). PROVENANCE_ENGINE read after cypher.py caused re-read of cypher.py for comparison. Step 2d had no prescriptive recipe, so agent grepped PROVENANCE_ENGINE.

### Fix applied (2026-04-11)
Phase 2 Step B: `grep -B1` now captures error code + file path together — Step C reads arrows.txt + changed.txt only, never lint.txt.
STOP gate: now enumerates forbidden files by name.
Step 2d: prescriptive recipe — Read PROVENANCE_ENGINE first, then fixture files; no grep/ls/scan.
Step 2e: "Do NOT re-read PROVENANCE_ENGINE.md — in context from 2d" added.
Critical rules: post-STOP lint file prohibition added.

## Run 20260411T173405 — Epic 6
- 48 calls, 33 necessary, 15 wasted (31% waste)
- Verdict: CLEAN
- Top waste patterns: **file-reread** (lint.txt 7×, cypher.py 5×), grep-storm (Phase 2 post-STOP, 4 calls)

### Root cause
Phase 2 Step C told agent to "Read lint.txt at arrow's line region per in-scope file" → N reads. cypher.py re-read because PROVENANCE_ENGINE arrived in context after cypher.py was read.

### Fix applied (2026-04-11)
See Run 20260411T174215 fixes above.

## Run 20260411T165551 — Epic 6
- 38 calls, 31 necessary, 7 wasted (18% waste)
- Verdict: LINT_FIXLIST_WRITTEN
- Top waste patterns: **grep-storm** (Phase 2, 4 calls), **demo-seed pre-grep** (Step 2e, 3 calls + 1 redundant read)

### Root cause
Phase 2: agent ran `grep -B 1` correctly (call #16) but then re-grepped 4x with Grep tool trying to correlate error codes with file paths in one regex shot. Mental correlation of interleaved paired lines is unreliable for Sonnet.
Step 2e: "do not grep first" prose prohibition failed 3x. Agent instinct is to orient before reading.

### Fix applied (2026-04-11)
Phase 2 replaced with 3-step file-based recipe: git diff → changed.txt, grep → arrows.txt, Read both + lint.txt offset for code lookup. Agent reads files instead of correlating in-head.
Step 2e replaced with explicit recipe: Read once (full file, <300 lines), scan in-context, STOP gate enforced.
agent-memory/project_tooling.md seeded with cypher.py file size + one-read rule.

## Run 20260411T163612 — Epic 6
- 50 calls, 25 necessary, 25 wasted (50% waste)
- Verdict: LINT_FIXLIST_WRITTEN
- Top waste pattern: **grep-storm**

### Root cause
Phase 2 said "use Read with offset/limit to find error codes" but the agent needs a line number to use an offset — which requires grepping. This created an irresolvable loop: grep → hit STOP rule → try Read without offset → fail → grep again. The STOP directive repeated 4x did not break the loop because the underlying algorithm made grepping necessary.

### Fix applied (2026-04-11)
Replaced two-command pattern (separate `git diff` + `grep -->`) with a single `grep -B 1` that returns error code + file path together. Agent now has everything from one pass; no further lint file access needed. STOP directive tightened to "Do not touch the lint file again."

### Secondary waste
- 2× `ls fixtures/` — fixed by adding known path + no-ls directive to Step 2d
- 3× re-reads of PROVENANCE_ENGINE.md and cypher.py — pre-existing "extract on first read" rule not enforced; watch on next run

## Run 20260411T162552 — Epic 6
- 48 calls, 28 necessary, 20 wasted (42% waste)
- Verdict: CLEAN
- Top waste pattern: file-reread
