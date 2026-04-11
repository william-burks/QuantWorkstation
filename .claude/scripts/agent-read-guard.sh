#!/bin/bash
# Guard script for lead-engineer Read PreToolUse hook.
# Blocks reading out-of-scope command files and limits re-reads of source files.
# Exit 0 = allow, Exit 2 = block (with reason on stderr).

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[ -z "$FILE" ] && exit 0

# Block reading other command files (verify-story, close-story)
# Catches scope-overreach pattern where agent reads wrong command file after Step 9.
if echo "$FILE" | grep -qE '\.claude/commands/close-story\.md$'; then
  echo "Blocked: lead-engineer cannot read close-story.md — orchestrator spawns close as a separate agent" >&2
  exit 2
fi

# Track and limit re-reads of source files.
# Uses /tmp/agent-read-tracker/ — reset by implement-story.md Step 0.
TRACK_DIR="/tmp/agent-read-tracker"
mkdir -p "$TRACK_DIR" 2>/dev/null || true

# Normalize to basename for tracking (unique basenames in this project).
BASENAME=$(basename "$FILE")

# Skip tracking for: memory files, story files, test files, docs, command files.
# Only track implementation source files likely to be re-read wastefully.
if echo "$BASENAME" | grep -qE '\.(md|yaml|yml|json|toml|cfg|txt)$'; then
  exit 0
fi
if echo "$BASENAME" | grep -qE '^(test_|conftest)'; then
  exit 0
fi

TRACK_FILE="$TRACK_DIR/$BASENAME"

if [ -f "$TRACK_FILE" ]; then
  COUNT=$(cat "$TRACK_FILE")
  NEWCOUNT=$((COUNT + 1))

  # Allow 1 initial read + 1 re-read (for Edit string mismatch recovery). Block 3+.
  if [ "$NEWCOUNT" -gt 2 ]; then
    echo "Blocked: $BASENAME already read ${COUNT}x — use context for Edit string matching. If Edit fails, read only the 20-line range around target (offset + limit params)." >&2
    exit 2
  fi
  echo "$NEWCOUNT" > "$TRACK_FILE"
else
  echo "1" > "$TRACK_FILE"
fi

exit 0
