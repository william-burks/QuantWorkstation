---
name: Agent Builder Bible
description: Canonical design principles and stylistic defaults for agent-builder. Read before any audit, fix proposal, or new agent design.
type: reference
---

# Agent Builder Bible

Accumulated principles from 10+ lead-engineer runs and 8+ qa-engineer runs.
These are structural laws — not guidelines. Apply to every command file, agent definition, and hook.

---

## 1. Prose prohibition fails at 100%

If an agent's default instinct is to do X, a bullet point saying "do NOT do X" will be ignored.
Confirmed across qa-engineer (8 runs), lead-engineer (3 runs).

**Law:** Every prohibition must be backed by a structural block. The prose is documentation, not enforcement.

| Prohibited behavior | Structural block |
|---|---|
| Read ruff/lint tools | agent-guard.sh exit 2 |
| Re-read files in context | agent-read-guard.sh exit 2 |
| Grep files already Read | agent-grep-guard.sh exit 2 |
| Bash grep tracked .py files | agent-guard.sh exit 2 |
| Grep Makefile | agent-guard.sh exit 2 |
| Run tools after STOP | agent-phase-gate.sh exit 2 |
| Re-initialize after STOP | agent-init-state.sh exit 1 if sentinel exists |

---

## 2. STOP GATE pattern (mandatory for terminal steps)

Every command file step that ends an agent's work uses this exact format:

```
**STOP GATE: <condition> → <action>. No further tool calls. No exceptions.**
```

Follow immediately with one sentence explaining the structural enforcement (which hook/guard fires).
Do NOT use bullet lists of "do NOT" items as the primary gate — they fail.

**Example (correct):**
```
**STOP GATE: Step 8 committed → output report below and STOP. No further tool calls. No exceptions.**

The phase gate (agent-phase-gate.sh) blocks all tools after Step 8. Do not attempt to re-run
agent-init-state.sh or read any command file. The orchestrator continues — you do not.
```

**Example (wrong — prose prohibition, will fail):**
```
**HARD STOP — your work is done. No further tool calls.**
- Do NOT read close-story.md
- Do NOT run any more tool calls
- The orchestrator will invoke verify-story next
```

The conditional form ("X committed → STOP") signals termination more cleanly than a list of prohibitions.

---

## 3. Init scripts must guard sentinel files

Any script that resets state (clears /tmp trackers, arms command sentinels) must check for
active phase gates before clearing them. Pattern:

```bash
if [ -f "/tmp/agent-step8-committed.txt" ]; then
  echo "ERROR: Phase gate is armed. Cannot re-initialize. Agent must STOP." >&2
  exit 1
fi
```

**Why:** An agent that calls agent-init-state.sh post-STOP disarms its own phase gate.
27 wasted calls in QWS-HF-001 run traced to this single failure point.

Apply this guard to any init script that touches sentinel files.

---

## 4. Self-disarming gate is a class of failure

Any sequence where an agent can call a script/command that removes the constraint blocking it
is a self-disarming gate. Examples:
- Calling agent-init-state.sh after Step 8 → clears sentinel
- Running `rm -f /tmp/agent-step8-committed.txt` directly → (now blocked by Bash guard)
- Calling a reset endpoint that clears feature flags

When designing guards: ask "can the agent call something that removes this guard?" If yes, add a check.

---

## 5. Tee pattern for test output

Agents running `make test` pipe through tail, lose detail, then re-run pytest targeted.
Standard recipe eliminates the second call:

```bash
make test 2>&1 | tee /tmp/test-output.txt | tail -60
```

If more detail needed: `cat /tmp/test-output.txt`. Do NOT re-run pytest.

This recipe belongs in:
1. The command file Step (where `make test` is invoked)
2. `project_tooling.md` agent memory

---

## 6. Discovery budget must be explicit and enforced by gate

Agents continue discovery (Grep/search_code) past the point of sufficient information.
Fix: put a hard gate after discovery ends.

**Pattern:**
```
**GATE: After all Repo Touchpoint files are read, discovery is OVER.
No more Grep/search_code until Step 4 edits fail. Any remaining questions → BLOCKED.**
```

Budget: max 2 search_code + 1 Grep per Repo Touchpoint file.
Never search the same symbol twice — combine into one pattern.

---

## 7. Bash grep on tracked files bypasses the Grep guard

The Grep tool guard (agent-grep-guard.sh) fires only on the Grep tool, not on Bash `grep`.
An agent that knows files are tracked will switch to `grep -n pattern file.py` via Bash.

Fix: agent-guard.sh checks if the Bash command matches `grep\b.*\.py` and the file basename
is in `/tmp/agent-read-tracker/`. Block with exit 2.

---

## 8. Large file protocol: grep-first, read targeted range

Files over 500 lines are NEVER read in full. Standard protocol:
1. `grep 'symbol_name' /tmp/symbol-index.txt` → get line N
2. `Read file.py offset=N limit=50`

If agent reads a full large file, diagnose which step failed to provide the line number.
Fix is usually: add a grep recipe to the Step 3 large-file table in the command file.

---

## 9. Makefile targets are documented — don't grep for them

Agents grep Makefile to verify target syntax despite exact commands being in the command file.
Blocked structurally: `grep.*Makefile` in agent-guard.sh.

When writing command files: always include the exact `make` invocation with all parameters.
Never leave the agent to infer syntax.

---

## 10. Efficiency baselines

| Agent | Target waste% | Current best | Primary waste pattern |
|---|---|---|---|
| lead-engineer | < 20% | 24% (R6/QWS-0801) | Post-STOP rampage, file-reread |
| qa-engineer | < 20% | TBD | TBD |
| lint-mechanic | < 10% | TBD | TBD |

When a run exceeds target: find root cause before proposing fix. Don't add more prose.
