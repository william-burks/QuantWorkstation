#!/bin/bash
# Unified discovery budget guard for search_code AND search_graph PreToolUse hooks.
# Both tools share a single counter — prevents tool-switching to evade per-tool caps.
# Cap: 10 total discovery MCP calls per story run.
# Exit 0 = allow, Exit 2 = block.
#
# Cap rationale: stories have 2-4 Repo Touchpoints × 2 calls each = 4-8 necessary.
# Cap of 10 allows 5 touchpoints at full budget before blocking bleed.
# Reset by agent-init-state.sh Step 0 (clears /tmp/agent-discovery-tracker/).

# Only enforce inside a lead-engineer run.
if [ ! -f "/tmp/agent-current-command.txt" ]; then
  exit 0
fi

TRACK_DIR="/tmp/agent-discovery-tracker"
mkdir -p "$TRACK_DIR" 2>/dev/null || true

COUNT_FILE="$TRACK_DIR/discovery_total_count"
CAP=10

if [ -f "$COUNT_FILE" ]; then
  COUNT=$(cat "$COUNT_FILE")
  if [ "$COUNT" -ge "$CAP" ]; then
    echo "Blocked: discovery MCP called ${COUNT}x — budget exhausted (cap=$CAP). Use context or read file directly." >&2
    exit 2
  fi
  echo "$((COUNT + 1))" > "$COUNT_FILE"
else
  echo "1" > "$COUNT_FILE"
fi

exit 0
