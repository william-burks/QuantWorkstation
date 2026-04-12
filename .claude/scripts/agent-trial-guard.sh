#!/bin/bash
# Guard script for trial-engineer PreToolUse hook.
# Reads JSON from stdin, blocks prohibited write paths and commands.
# Exit 0 = allow, Exit 2 = block (with reason on stderr).

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# --- Bash tool blocks ---
if [ "$TOOL" = "Bash" ] && [ -n "$COMMAND" ]; then

  # Block qw abort
  if echo "$COMMAND" | grep -qE 'qw\s+abort'; then
    echo "Blocked: trial-engineer cannot abort strategies" >&2
    exit 2
  fi

  # Block qw degrade
  if echo "$COMMAND" | grep -qE 'qw\s+degrade'; then
    echo "Blocked: trial-engineer cannot degrade champions" >&2
    exit 2
  fi

  # Block qw retire
  if echo "$COMMAND" | grep -qE 'qw\s+retire'; then
    echo "Blocked: trial-engineer cannot retire champions" >&2
    exit 2
  fi

  # Block qw champion (no promotion)
  if echo "$COMMAND" | grep -qE 'qw\s+champion'; then
    echo "Blocked: trial-engineer cannot promote champions — report metrics, let Will decide" >&2
    exit 2
  fi

  # Block git commit
  if echo "$COMMAND" | grep -qE 'git\s+commit'; then
    echo "Blocked: trial-engineer cannot commit" >&2
    exit 2
  fi

  # Block git push
  if echo "$COMMAND" | grep -qE 'git\s+push'; then
    echo "Blocked: trial-engineer cannot push" >&2
    exit 2
  fi

fi

# --- Write/Edit tool blocks ---
if [ "$TOOL" = "Write" ] || [ "$TOOL" = "Edit" ]; then
  if [ -n "$FILE_PATH" ]; then

    # Block writes to execution/
    if echo "$FILE_PATH" | grep -qE '(^|/)execution/'; then
      echo "Blocked: trial-engineer cannot write to execution/ — OMS and risk engine are off-limits" >&2
      exit 2
    fi

    # Block writes to data/collectors/
    if echo "$FILE_PATH" | grep -qE '(^|/)data/collectors/'; then
      echo "Blocked: trial-engineer cannot write to data/collectors/" >&2
      exit 2
    fi

    # Block writes to research/experiments/*.py (harness files)
    if echo "$FILE_PATH" | grep -qE 'research/experiments/[^/]+\.py$'; then
      echo "Blocked: trial-engineer cannot modify research/experiments/*.py — harness is stable" >&2
      exit 2
    fi

  fi
fi

exit 0
