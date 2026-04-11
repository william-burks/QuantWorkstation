Pre-flight validation for QuantWorkstation epic: $ARGUMENTS

Format: `/preflight <epic_number>`

Runs readiness check + strategic validation in isolation. Does NOT start implementation.
Designed for incremental audit extension — each agent spawn is a discrete, traceable step.

## Step 0 — Generate run_id
```
date -u +%Y%m%dT%H%M%S
```
Save output as RUN_ID.

## Step 1 — Clean stale traces
```
rm -f /tmp/agent-trace-product-analyst-*.jsonl 2>/dev/null || true
rm -f /tmp/agent-trace-qws-architect-*.jsonl 2>/dev/null || true
```

## Step 2 — Readiness check (product-analyst, Haiku)
Spawn product-analyst agent:
```
Read qws_graph/epics/INDEX.md and docs/BACKLOG_ALIGNMENT.md.
For epic $ARGUMENTS check:
1. Any story not `ready` (draft, TESTING, BLOCKED)?
2. Any story with unresolved dependencies (blocked-on not CLOSED)?
3. Neo4j reachable? Run: make -C qws_graph neo4j-status
4. Latest release branch name (git branch | grep release/ | sort -V | tail -1)?
Return: READY_TO_RUN | BLOCKED — one line per issue. Max 10 lines total.
```

If BLOCKED → report issues and STOP. Do not proceed to strategic validation.

## Step 3 — Strategic validation (qws-architect, Opus)
Spawn qws-architect agent:
```
Load: docs/MANIFESTO.md, docs/RESEARCH_WORKFLOW.md, docs/PROVENANCE_ENGINE.md, docs/BACKLOG_ALIGNMENT.md
Load: all story files for epic $ARGUMENTS in qws_graph/epics/

Validate:
1. Do these stories collectively build toward the target exocortex?
2. Any story that passes validation but points in the wrong direction?
3. Schema drift between PROVENANCE_ENGINE and story touchpoints?
4. Dependency chains circular or missing?
5. Sprint sequence optimal — does order maximize capability unlock?

Report: ALIGNED | MISALIGNED (with specific findings per story)
```

If MISALIGNED → report findings and STOP. Flag for Will to resolve before running.

## Step 4 — Report
```
## Epic $ARGUMENTS — Pre-flight Report (run_id: <RUN_ID>)

### Readiness
READY_TO_RUN | BLOCKED
[product-analyst findings]

### Strategic alignment
ALIGNED | MISALIGNED
[qws-architect findings]

### Verdict
CLEAR — safe to run: /run-epic $ARGUMENTS
BLOCKED — resolve issues above before running
```

## Step 5 — Cleanup
```
rm -f /tmp/agent-trace-product-analyst-*.jsonl 2>/dev/null || true
rm -f /tmp/agent-trace-qws-architect-*.jsonl 2>/dev/null || true
```

<!-- AUDIT HOOK: to add audit on product-analyst or qws-architect, insert between Step 3 and Step 4:
     mv trace → story-keyed name, spawn qa-auditor with relevant command file, append to preflight_runs.csv -->
