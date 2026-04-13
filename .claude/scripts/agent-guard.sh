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

# Block all ruff execution paths — lint-mechanic handles ruff fixes
if echo "$COMMAND" | grep -qiE '(^|\s|&&\s*|;\s*)ruff\s'; then
  echo "Blocked: lead-engineer cannot run ruff directly — spawn lint-mechanic instead" >&2
  exit 2
fi

# Block make lint — runs ruff
if echo "$COMMAND" | grep -qE 'make\s+lint(\s|$)'; then
  echo "Blocked: make lint runs ruff — use 'make typecheck' for mypy or 'make test' for pytest" >&2
  exit 2
fi

# Block make check — includes ruff via lint
if echo "$COMMAND" | grep -qE 'make\s+check(\s|$)'; then
  echo "Blocked: make check includes ruff — use 'make typecheck' and 'make test' separately" >&2
  exit 2
fi

# Block Bash grep on Makefile — target syntax is documented in command files
if echo "$COMMAND" | grep -qE 'grep\b.*Makefile|grep\b.*makefile'; then
  echo "Blocked: do not grep Makefile — target syntax is in the command file" >&2
  exit 2
fi

# Block Bash grep on source files already in read-tracker (use context instead)
if echo "$COMMAND" | grep -qE 'grep\b.*\.(py|yaml|yml|toml)'; then
  TARGET_FILE=$(echo "$COMMAND" | grep -oE '[^ ]+\.(py|yaml|yml|toml)' | tail -1 | xargs basename 2>/dev/null)
  if [ -n "$TARGET_FILE" ] && [ -f "/tmp/agent-read-tracker/$TARGET_FILE" ]; then
    echo "Blocked: $TARGET_FILE is already in context — search context instead of Bash grep" >&2
    exit 2
  fi
fi

exit 0