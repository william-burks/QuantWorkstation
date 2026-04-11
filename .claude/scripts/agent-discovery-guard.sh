#!/bin/bash
# Guard for mcp__codebase-memory-mcp__search_code PreToolUse hook.
# Caps total search_code calls per story run to enforce discovery budget.
# Exit 0 = allow, Exit 2 = block.
#
# Cap rationale: stories have 2-4 Repo Touchpoints × 2 calls each = 4-8 necessary.
# Cap of 10 allows 5 touchpoints at full budget before blocking bleed.
# Reset by implement-story.md Step 0.

TRACK_DIR="/tmp/agent-discovery-tracker"
mkdir -p "$TRACK_DIR" 2>/dev/null || true

COUNT_FILE="$TRACK_DIR/search_code_count"
CAP=10

if [ -f "$COUNT_FILE" ]; then
  COUNT=$(cat "$COUNT_FILE")
  if [ "$COUNT" -ge "$CAP" ]; then
    echo "Blocked: search_code called ${COUNT}x — discovery budget exhausted (cap=$CAP). Read known file directly or use context." >&2
    exit 2
  fi
  echo "$((COUNT + 1))" > "$COUNT_FILE"
else
  echo "1" > "$COUNT_FILE"
fi

exit 0
