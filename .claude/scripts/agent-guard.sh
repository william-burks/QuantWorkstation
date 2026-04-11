#!/bin/bash
# Guard script for lead-engineer PreToolUse hook.
# Reads JSON from stdin, blocks dangerous commands.
# Exit 0 = allow, Exit 2 = block (with reason on stderr).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# Block git add -A or git add .
if echo "$COMMAND" | grep -qE 'git\s+add\s+(-A|\.)'; then
  echo "Blocked: use 'git add <specific files>' — never git add -A or git add ." >&2
  exit 2
fi

# Block git push (lead-engineer should never push)
if echo "$COMMAND" | grep -qE 'git\s+push'; then
  echo "Blocked: lead-engineer cannot push — orchestrator handles push via make to-release" >&2
  exit 2
fi

# Block writes to .env files
if echo "$COMMAND" | grep -qE '>\s*\.env|cat.*>.*\.env|echo.*>.*\.env'; then
  echo "Blocked: cannot write to .env files" >&2
  exit 2
fi

# Block repo-wiping rm -rf (root dir, ., ..)
if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+(/|\./?\.?\s)'; then
  echo "Blocked: recursive delete of root/repo directory not allowed" >&2
  exit 2
fi

exit 0