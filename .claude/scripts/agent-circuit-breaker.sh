#!/bin/bash
# PostToolUse circuit breaker for Bash tool.
# Tracks (command_basename, error_class) pairs. Blocks next tool call on 3rd identical failure.
# Only fires on non-zero exit or recognized error patterns in output.
# Exit 0 = allow next tool, Exit 2 = block next tool (circuit break).

# No-op outside lead-engineer runs (sentinel gate — same as read guard).
if [ ! -f "/tmp/agent-current-command.txt" ]; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
OUTPUT=$(echo "$INPUT" | jq -r '.tool_response // empty')
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# --- Fix 7: Edit-thrash circuit breaker ---
# If this is an Edit tool call, track consecutive failures on same file.
if [ "$TOOL" = "Edit" ]; then
  FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
  RESPONSE=$(echo "$INPUT" | jq -r '.tool_response // empty')
  [ -z "$FILE" ] && exit 0
  # Check if Edit failed (string not found in file)
  if echo "$RESPONSE" | grep -qiE 'not found|no match|string.*not|failed'; then
    FNAME=$(basename "$FILE")
    EDIT_KEY="edit_fail__${FNAME}"
    EDIT_KEY=$(echo "$EDIT_KEY" | tr ' []/' '____' | tr -cd '[:alnum:]_-' | cut -c1-80)
    EDIT_FILE="$TRACK_DIR/$EDIT_KEY"
    mkdir -p "$TRACK_DIR" 2>/dev/null || true
    if [ -f "$EDIT_FILE" ]; then
      COUNT=$(cat "$EDIT_FILE")
      NEWCOUNT=$((COUNT + 1))
      echo "$NEWCOUNT" > "$EDIT_FILE"
      if [ "$NEWCOUNT" -ge 3 ]; then
        echo "CIRCUIT BREAK: Edit on '$FNAME' failed ${NEWCOUNT}x — stop trying Edit. Use Read with offset+limit to get the exact 20-line range around your target, then retry once." >&2
        exit 2
      fi
    else
      echo "1" > "$EDIT_FILE"
    fi
  else
    # Edit succeeded — reset failure counter for this file
    FNAME=$(basename "$FILE")
    EDIT_KEY="edit_fail__${FNAME}"
    EDIT_KEY=$(echo "$EDIT_KEY" | tr ' []/' '____' | tr -cd '[:alnum:]_-' | cut -c1-80)
    rm -f "$TRACK_DIR/$EDIT_KEY" 2>/dev/null || true
  fi
  exit 0
fi

[ -z "$COMMAND" ] && exit 0
[ -z "$OUTPUT" ] && exit 0

TRACK_DIR="/tmp/circuit-breaker"
mkdir -p "$TRACK_DIR" 2>/dev/null || true

# --- Extract command basename (first token, strip path) ---
FIRST_TOKEN=$(echo "$COMMAND" | awk '{print $1}')
CMD_BASE=$(basename "$FIRST_TOKEN")

# For make targets, include the target name (make test ≠ make typecheck)
if [ "$CMD_BASE" = "make" ]; then
  TARGET=$(echo "$COMMAND" | awk '{print $2}')
  CMD_BASE="make_${TARGET}"
fi

# --- Extract error class from output ---
# mypy: "error: ... [error-code]"
ERROR_CLASS=$(echo "$OUTPUT" | grep -oE 'error: .*\[[a-z-]+\]' | head -1 | grep -oE '\[[a-z-]+\]' | head -1)

# pytest: "FAILED tests/...::TestName"
if [ -z "$ERROR_CLASS" ]; then
  ERROR_CLASS=$(echo "$OUTPUT" | grep -oE 'FAILED [^ ]+' | head -1)
fi

# CLI error: "Error: ..." first line
if [ -z "$ERROR_CLASS" ]; then
  ERROR_CLASS=$(echo "$OUTPUT" | grep -m1 -oE '^Error: [^\n]{1,60}')
fi

# make error: "Error N" or "recipe for target X failed"
if [ -z "$ERROR_CLASS" ]; then
  ERROR_CLASS=$(echo "$OUTPUT" | grep -m1 -oE 'Error [0-9]+|recipe for target .* failed')
fi

# No recognizable error pattern → not a failure worth tracking
[ -z "$ERROR_CLASS" ] && exit 0

# --- Track and enforce ---
# Key: cmd_base + error_class, normalized (spaces→underscores, brackets removed)
KEY=$(echo "${CMD_BASE}__${ERROR_CLASS}" | tr ' []/' '____' | tr -cd '[:alnum:]_-' | cut -c1-80)
TRACK_FILE="$TRACK_DIR/$KEY"

if [ -f "$TRACK_FILE" ]; then
  COUNT=$(cat "$TRACK_FILE")
  NEWCOUNT=$((COUNT + 1))
  echo "$NEWCOUNT" > "$TRACK_FILE"
  if [ "$NEWCOUNT" -ge 3 ]; then
    echo "CIRCUIT BREAK: '$CMD_BASE' has failed with '$ERROR_CLASS' ${NEWCOUNT}x — stop retrying this approach. Diagnose root cause from the error above, or report BLOCKED." >&2
    exit 2
  fi
else
  echo "1" > "$TRACK_FILE"
fi

exit 0
