Run two QuantWorkstation epics end-to-end, sequentially, with no user input between them.

Format: `/extreme-programming <epic_n> <epic_m>`

EPIC_N = first argument
EPIC_M = second argument

This skill runs in the **main session** as orchestrator. Do not wait for user input at any point. If a story needs assumption resolution, follow the run-epic assumption flow autonomously. Stop only on unrecoverable BLOCKED/FAILED with no dependents left.

---

## Phase 1 — Run EPIC_N end-to-end

Execute `.claude/commands/run-epic.md` for EPIC_N in full:
- Run Steps 0a through 5 exactly as specified in run-epic.md
- After Step 5 (post-epic QA) completes CLEAN: proceed to close

**Close EPIC_N:**
Execute `.claude/commands/close-epic.md` for EPIC_N.
The close-epic STOP GATE fires inside the agent — the orchestrator (this session) continues regardless.

**If EPIC_N has any FAILED/BLOCKED stories with no path forward:**
Stop. Print:
```
EPIC_N: FAILED — <story list> blocked/failed
EPIC_M: SKIPPED — prerequisite epic did not complete
```
Do not proceed to Phase 2.

---

## Phase 2 — Run EPIC_M end-to-end

Execute `.claude/commands/run-epic.md` for EPIC_M in full:
- Run Steps 0a through 5 exactly as specified in run-epic.md
- After Step 5 (post-epic QA) completes CLEAN: proceed to close

**Close EPIC_M:**
Execute `.claude/commands/close-epic.md` for EPIC_M.

---

## Final Report

```
## Extreme Programming — Complete

### EPIC_N
<COMPLETE | FAILED> — <N stories closed, M skipped>

### EPIC_M
<COMPLETE | FAILED | SKIPPED> — <N stories closed, M skipped>

### Capabilities delivered
[combined bullet list across both epics]

### Next
[next unblocked epic or story per BACKLOG_ALIGNMENT.md]
```
