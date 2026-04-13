Implement the QuantWorkstation story identified by: $ARGUMENTS

## Step 0 — Read memory (MANDATORY FIRST)
```bash
bash .claude/scripts/agent-init-state.sh implement-story
```
Read `.claude/agent-memory/lead-engineer/MEMORY.md` and all referenced files BEFORE any tool invocations.
Use the exact commands documented there for tests, lint, and type checking.
Do NOT attempt ruff, pytest, or mypy without checking memory for the correct invocation.

## Step 1 — Locate story
```bash
STORY_FILE=$(.claude/scripts/locate-story.sh $ARGUMENTS)
```
If exit 1 → report BLOCKED (story not found).
Read the file at `$STORY_FILE`. Stop if Status ≠ `READY`.
**Story file is now in context — do NOT re-read it during Steps 4 or 7.**

## Step 2 — Verify unblocked
Read `docs/BACKLOG_ALIGNMENT.md` "Blocked On" column. If blocked → stop, report blocker.

## Step 3 — Read context
Read docs directly (known locations):
- `docs/PROVENANCE_ENGINE.md`
- `docs/BACKLOG_ALIGNMENT.md`

**PROVENANCE_ENGINE.md and BACKLOG_ALIGNMENT.md are now in context — do NOT re-read them in any later step.**

For each symbol in "Repo Touchpoints":

**Step A — search_graph (always first for functions/classes, uncapped):**
`search_graph(project="Users-will-ClaudeProjects-QuantWorkstation", label="Function", name_pattern="symbol_name")` → note `qualified_name` + `start_line` → `get_code_snippet(project="Users-will-ClaudeProjects-QuantWorkstation", qualified_name=...)`. Two MCP calls. Returns exact line range — no guessing.
Full file anchor map: `search_graph(..., file_pattern="*cli.py", limit=50)` → all functions in one call.

**Step B — only if Step A misses** (constant, config var, or graph not yet indexed):
```bash
grep 'SymbolName' /tmp/symbol-index.txt
```
Returns `filename.py:lineN:    def method_name`. Read only that 50-line range. One Bash call.

**Step C — only if both A and B miss:**
One targeted Grep on the most relevant file. No broad patterns.

Never skip A. Never search the same symbol twice (prefix/suffix variants = same symbol). Never search the same keyword twice — if a Grep includes term X, no subsequent Grep may include X. Combine into one pattern.

**Discovery budget: max 2 search_code + 1 Grep per Repo Touchpoint file. After reading matched files, STOP discovery and start editing.**

**GATE: After all Repo Touchpoint files are read, discovery is OVER. No more Grep/search_code calls until Step 4 edits fail (string mismatch). Any remaining questions → resolve from context or report BLOCKED.**

**Large file protocol — read targeted ranges only, never full file:**
| File | Size | How to target |
|------|------|--------------|
| `store.py` | ~1400L | `grep 'method_name' /tmp/symbol-index.txt` → read only that 50-line range |
| `cli.py` | ~1550L | `argparse` CLI — NOT click/typer. `grep 'cmd_name' /tmp/symbol-index.txt` → line number. Or `search_graph(project="Users-will-ClaudeProjects-QuantWorkstation", label="Function", file_pattern="*cli.py", limit=50)` for full anchor map in one call. Returns qualified_name + start_line + end_line for all 18 functions. |
| `cypher.py` | ~700L | `grep 'DEMO_SEED_CYPHER' /tmp/symbol-index.txt` → if miss, known offset ~465, read 200-line range |
| `query.py` | ~540L | `grep 'constant_name' /tmp/symbol-index.txt` → read that range |
| `data_dictionary.yaml` | ~1100L | `grep 'NodeOrEdgeName' /tmp/schema-index.txt` → get line N → `Read data_dictionary.yaml offset=N limit=40`. ONE Edit per node/edge block — compose the ENTIRE block (all properties) in one `new_string`. Max 2 Edit calls for this file. Never read the full file. |

Never exceed 200 lines in a single Read of these files. Read once, edit from context.

No [TARGET] nodes/relationships/MCP tools unless this story implements them.

**STOP — do NOT re-read for reference: PROVENANCE_ENGINE.md, BACKLOG_ALIGNMENT.md, story file, data_dictionary.yaml, graph_v1_contract.md. If you need to Edit these files later, use exact strings from context. If Edit fails string match, read ONLY the 20-line range around the target — not the whole file.**

If any schema, design, or scope question cannot be resolved from these docs → do not guess.
```
echo "<exact question>" > /tmp/assumption_$ARGUMENTS.txt
git add <story file>
git commit -m "blocked($ARGUMENTS): assumption — <exact question>"
```
Report: `BLOCKED | assumption | <exact question>` and stop.

If `/tmp/ruling_$ARGUMENTS.txt` exists → read it before reporting blocked. Apply ruling and continue.

## Step 4 — Implement
**SCOPE-LOCK (hard constraint):** Only edit files explicitly listed in the story's Repo Touchpoints. If a file is not listed, do NOT edit it — even if it looks related. No inferred-in-scope edits.

**Files read in Step 3 are in context. Do NOT re-read them before editing. Use exact strings from context for Edit `old_string`. If an Edit fails due to string mismatch, read ONLY the 20-line range around the target — not the whole file.**
**graph_v1_contract.md, data_dictionary.yaml, PROVENANCE_ENGINE.md:** read in Step 3, edit from context in Step 4. Do NOT re-read before editing — compose `old_string` from what is already in context.

Work ACs one by one. After each:
1. Story checkboxes — do NOT edit story file during Step 4. Wait until Step 5 (test plan) and batch ALL checkbox updates + test plan into ONE Edit call. If Step 7 finds failures, that's the 2nd allowed edit. **Max 2 Edit calls to story file total.**
2. `git add` each changed file (never `-A` or `.`)
3. `make test 2>&1 | tee /tmp/test-output.txt | tail -60` after any Python change — if failures need detail, `cat /tmp/test-output.txt`. Do NOT re-run pytest separately.
4. Run `make typecheck` on the project. Baseline is **0 errors** — any failure = you introduced it. Read ALL errors, fix ALL in one pass, re-run once. Max 2 cycles.

**data_dictionary.yaml edits:** Use `grep 'NodeOrEdgeName' /tmp/schema-index.txt` → get line N → `Read offset=N limit=40`. Compose the ENTIRE node or edge block (all properties) in ONE `new_string`. Max 2 Edit calls total for this file — one for nodes section, one for relationships section.

For large files (>500 lines): grep for the target function/section first, then read only that range.
Do NOT read whole files in sequential chunks.
**`cat -n` targeted reads count toward the file re-read limit.** One range per section — do NOT read sequential adjacent ranges. If you need 100 lines, read 100 lines in one call, not 2×50.
**Edit = verified. Do NOT grep a file after editing it to confirm the change — the Edit tool confirms success.**

**Lint is handled at QA phase — do NOT run ruff during implementation.**
`ruff`, `make lint`, and `make check` are structurally blocked by agent-guard.sh. Type check only: `make typecheck`.

**4b — Demo seed.** If this story adds or modifies nodes, edges, or properties:
update `DEMO_SEED_CYPHER` and `DEMO_TEARDOWN_CYPHER` in `qws_graph/research/graph/cypher.py`.
`cypher.py` is ~700 lines — grep for `DEMO_SEED_CYPHER` first (~line 465), then Read that offset range only. Do NOT read the whole file. Do NOT re-read cypher.py after this step.
New node types → add MERGE block (`is_demo=true`, deterministic IDs, realistic values).
Modified properties → update existing SET blocks. This is part of implementation, not verification.

## Step 5 — Write Acceptance Test Plan
**This is your ONLY Edit to the story file — include ALL checkbox updates from Step 4 + the test plan in ONE Edit call. A second Edit to the story file here is waste.**
Add `## Acceptance Test Plan` section to story file after ACs.

```markdown
### AC1: <description>
- type: cli | cypher | file_check | regression
- cmd: <exact command>
- expect_contains: "<substring>"
- expect_exit: 0
```

Types: `cli` (qw command + exit/output), `cypher` (Neo4j query + result), `file_check` (path exists/content), `regression` (two commands match).

Rules: demo seed IDs only. Never real data. Generate fixtures/scripts as needed. Every AC ≥ 1 test step.

## Step 6 — Commit implementation
```
git add <files by name>
make commit-impl STORY=$ARGUMENTS MSG="<summary>"
```
These Makefile targets are exact — do NOT grep Makefile to verify syntax. `commit-impl` takes `STORY=` and optional `MSG=`. `commit-story-status` takes `STORY=` and optional `MSG=`.

## Step 7 — Execute acceptance tests (fail/fix cycle)
Run each test step. Compare actual vs expected.
**One `ls` per directory — if result answers the question, stop. Do NOT drill into subdirectories.**
**Do NOT re-run the full test suite if no code changed since the last passing run.**

Passing AC → confirm `- [x]`.

**On failure:**
1. Mark AC: `- [FAILED] AC<N> — <actual vs expected>`
2. `git commit -m "fail($ARGUMENTS): AC<N> — <failure>"`
3. Diagnose + fix code
4. Restore `- [x]`
5. `git commit -m "fix($ARGUMENTS): AC<N> — <what fixed>"`
6. Re-run ALL tests from top
7. Max 3 cycles → commit blocked state + stop:
   ```
   git add <story file>
   git commit -m "blocked($ARGUMENTS): AC<N> — max cycles, <reason>"
   ```
   Report: `BLOCKED | <reason>` and stop.

## Step 8 — Update status
All ACs pass → update story file, INDEX.md, and BACKLOG_ALIGNMENT.md in one call:
```bash
.claude/scripts/set-story-status.sh $ARGUMENTS TESTING
```
Then commit atomically (stages all modified tracked files + arms phase gate):
```
make commit-story-status STORY=$ARGUMENTS
```
Do NOT run git add or echo the sentinel separately — the make target does both.

## Step 9 — Report and STOP

**STOP GATE: Step 8 committed → output report below and STOP. No further tool calls. No exceptions.**

The phase gate (agent-phase-gate.sh) blocks all tools after Step 8. Do not attempt to read verify-story.md, re-run agent-init-state.sh, re-locate the story, or run any command. The orchestrator invokes verify-story — you do not.

```
## $ARGUMENTS — Implemented and Self-Tested

### Changes
[file-by-file bullets]

### Acceptance Tests
| AC | Status | Notes |
|----|--------|-------|

### Fix cycles
[fail/fix commits if any]

### Quality
[pytest result]

### Generated test data
[new fixtures/scripts]
```

Final status: **TESTING** or **BLOCKED** (with details).