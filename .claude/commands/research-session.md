# Research Session Protocol

## Step 0 — Prime trace sentinel
Before spawning any agent:
```
echo "research-navigator" > /tmp/agent-trace-active.txt
```

## Step 1 — Spawn research-navigator
Pass the user's message (or empty string if none) as the agent prompt.
The research-navigator agent owns all phases: session start (graph screening + shortlist), redundancy check, pivot analysis, and session wrap.

Do not re-implement phases here. The agent definition is the source of truth.

## Step 2 — When spawning trial-engineer (from within session)
Before spawning trial-engineer, update the sentinel:
```
echo "trial-engineer" > /tmp/agent-trace-active.txt
```
After trial-engineer returns, restore:
```
echo "research-navigator" > /tmp/agent-trace-active.txt
```

## Step 3 — Cleanup
After session ends:
```
rm -f /tmp/agent-trace-active.txt
```
Trace files remain at `/tmp/agent-trace-research-navigator-*.jsonl` and `/tmp/agent-trace-trial-engineer-*.jsonl` for audit.
