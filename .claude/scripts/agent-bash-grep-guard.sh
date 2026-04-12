#!/bin/bash
# Guard for Bash PreToolUse hook (settings.json global — safe for all agents).
# ONLY blocks: grep/rg commands targeting .py files already in the read tracker.
# Does NOT block: ruff, git push, or any other lead-engineer-specific rules
# (those are in agent-guard.sh in lead-engineer.md frontmatter).
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# Only intercept grep/rg commands
if ! echo "$COMMAND" | grep -qE '(^|\s)(grep|rg)\s'; then
  exit 0
fi

TRACK_DIR="/tmp/agent-read-tracker"
[ -d "$TRACK_DIR" ] || exit 0

# Extract .py filenames from the command and check tracker
# Match tokens ending in .py (handles paths like qws_graph/research/graph/store.py)
for token in $COMMAND; do
  if echo "$token" | grep -qE '\.py$'; then
    BASENAME=$(basename "$token")
    if [ -f "$TRACK_DIR/$BASENAME" ]; then
      echo "Blocked: grep on $BASENAME — already Read (use context window instead of filesystem)" >&2
      exit 2
    fi
  fi
done

exit 0
