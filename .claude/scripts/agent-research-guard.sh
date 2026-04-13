#!/bin/bash
# Guard script for research-navigator PreToolUse hook.
# Reads JSON from stdin, blocks prohibited commands and write paths.
# Exit 0 = allow, Exit 2 = block (with reason on stderr).

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# --- Bash tool blocks ---
if [ "$TOOL" = "Bash" ] && [ -n "$COMMAND" ]; then

  # Block trial execution via python research/
  if echo "$COMMAND" | grep -qE '(^|\s|&&\s*|;\s*)python\s+(research/|research\.)'; then
    echo "Blocked: research-navigator cannot execute trials — spawn trial-engineer instead" >&2
    exit 2
  fi

  # Block python -m research
  if echo "$COMMAND" | grep -qE 'python\s+-m\s+research'; then
    echo "Blocked: research-navigator cannot execute trials — spawn trial-engineer instead" >&2
    exit 2
  fi

  # Block research/bin/ shell runners
  if echo "$COMMAND" | grep -qE 'research/bin/'; then
    echo "Blocked: research-navigator cannot run shell runners — spawn trial-engineer instead" >&2
    exit 2
  fi

  # Block qw record --bundle
  if echo "$COMMAND" | grep -qE 'qw\s+record\s+--bundle'; then
    echo "Blocked: research-navigator cannot ingest results — spawn trial-engineer instead" >&2
    exit 2
  fi

  # Block qw abort
  if echo "$COMMAND" | grep -qE 'qw\s+abort'; then
    echo "Blocked: research-navigator cannot abort strategies" >&2
    exit 2
  fi

  # Block qw degrade
  if echo "$COMMAND" | grep -qE 'qw\s+degrade'; then
    echo "Blocked: research-navigator cannot degrade champions" >&2
    exit 2
  fi

  # Block qw retire
  if echo "$COMMAND" | grep -qE 'qw\s+retire'; then
    echo "Blocked: research-navigator cannot retire champions" >&2
    exit 2
  fi

  # Block qw monitor
  if echo "$COMMAND" | grep -qE 'qw\s+monitor'; then
    echo "Blocked: research-navigator cannot run qw monitor" >&2
    exit 2
  fi

  # Block git commit
  if echo "$COMMAND" | grep -qE 'git\s+commit'; then
    echo "Blocked: research-navigator cannot commit" >&2
    exit 2
  fi

  # Block git push
  if echo "$COMMAND" | grep -qE 'git\s+push'; then
    echo "Blocked: research-navigator cannot push" >&2
    exit 2
  fi

fi

# --- Write tool blocks ---
if [ "$TOOL" = "Write" ] && [ -n "$FILE_PATH" ]; then

  # Only allow writes to research/ideas/
  if ! echo "$FILE_PATH" | grep -qE 'research/ideas/'; then
    echo "Blocked: research-navigator can only write to research/ideas/ — got: $FILE_PATH" >&2
    exit 2
  fi

fi

exit 0
