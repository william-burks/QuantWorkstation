#!/bin/bash
# Guard for Grep PreToolUse hook.
# Blocks Grep on source files already Read (tracked by agent-read-guard.sh).
# "Do NOT Grep a file already in context" — structural enforcement.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.path // empty')

# No path = global grep (discovery pattern) — allow
[ -z "$FILE" ] && exit 0

BASENAME=$(basename "$FILE")

# No dot in basename = directory or glob pattern — allow
if ! echo "$BASENAME" | grep -q '\.'; then
  exit 0
fi

# Fix 2C: Skip only files that read-guard never tracks (json/toml/cfg/txt + test files)
# .yaml/.yml and qws_graph .md are now tracked by read-guard — check them here too
if echo "$BASENAME" | grep -qE '\.(json|toml|cfg|txt)$'; then
  exit 0
fi
if echo "$BASENAME" | grep -qE '^(test_|conftest)'; then
  exit 0
fi

# If this file was Read, it's in context — Grep is redundant
TRACK_DIR="/tmp/agent-read-tracker"
if [ -f "$TRACK_DIR/$BASENAME" ]; then
  echo "Blocked: $BASENAME already Read — search context instead of re-grepping. For line offsets, use Read with offset+limit on the target range." >&2
  exit 2
fi

exit 0
