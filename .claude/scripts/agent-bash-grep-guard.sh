#!/bin/bash
# Guard for Bash PreToolUse hook (settings.json global — safe for all agents).
# Blocks:
#   1. ALL bare mypy invocations (file, directory, or piped) — use make typecheck
#   2. sed/awk/nl on ANY .py file (unconditional — use Read+offset instead)
#   3. cat -n on .py files: tracked, blocked on 3rd+ access (2-read cap, same as Read guard)
#   4. grep/rg/head/tail on .py/.yaml/.md files already in the read tracker
# Does NOT block: ruff, git push, or lead-engineer-specific rules (those are in agent-guard.sh).
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

TRACK_DIR="/tmp/agent-read-tracker"

# Fix 3: Block ALL bare mypy invocations — use 'make typecheck' only.
# Catches: mypy file.py, mypy --strict dir/, mypy --strict dir/ | awk '...'
# Does NOT match: make typecheck (starts with 'make', not 'mypy')
if echo "$COMMAND" | grep -qE '(^|\s|&&\s*|;\s*)mypy\s'; then
  echo "Blocked: bare mypy — use 'make typecheck' for type checking (max 2 cycles)" >&2
  exit 2
fi

# Fix 2: Block sed/awk/nl on .py files — unconditional (no tracker required).
# Per pipe segment to avoid false positives from pipelines.
if echo "$COMMAND" | grep -qE '(^|\|)[^|]*(sed|awk|nl)\s'; then
  IFS='|' read -ra SEGMENTS <<< "$COMMAND"
  for segment in "${SEGMENTS[@]}"; do
    if echo "$segment" | grep -qE '(^|\s)(sed|awk|nl)\s'; then
      for token in $segment; do
        if echo "$token" | grep -qE '\.(py|yaml|yml|md)$'; then
          FNAME=$(basename "$token")
          echo "Blocked: $FNAME — use 'Read' tool with offset+limit for targeted source reads (sed/awk/nl not allowed)" >&2
          exit 2
        fi
      done
    fi
  done
fi

# Fix 8: Block cp of source files to /tmp/ — prevents read-guard bypass via snapshot renaming.
# Pattern: cp store.py /tmp/store_snapshot.py → Read /tmp/store_snapshot.py bypasses tracker.
if echo "$COMMAND" | grep -qE '(^|\s|&&\s*|;\s*)cp\s'; then
  if echo "$COMMAND" | grep -qE '\.(py|yaml|yml|md)\s.*/tmp/'; then
    echo "Blocked: cp source files to /tmp/ — use Read tool with offset+limit for targeted reads (snapshot bypass not allowed)" >&2
    exit 2
  fi
fi

# Fix 1: Track cat -n on .py files (2-read cap, same as Read guard).
# cat -n is the correct targeted-range tool — allow first 2 accesses, block 3rd+.
if echo "$COMMAND" | grep -qE '(^|\s)cat\s+-n\s'; then
  [ -d "$TRACK_DIR" ] || exit 0
  IFS='|' read -ra SEGMENTS <<< "$COMMAND"
  for segment in "${SEGMENTS[@]}"; do
    if echo "$segment" | grep -qE '(^|\s)cat\s+-n\s'; then
      for token in $segment; do
        if echo "$token" | grep -qE '\.py$'; then
          FNAME=$(basename "$token")
          CAT_FILE="$TRACK_DIR/catn_${FNAME}"
          if [ -f "$CAT_FILE" ]; then
            COUNT=$(cat "$CAT_FILE")
            NEWCOUNT=$((COUNT + 1))
            if [ "$NEWCOUNT" -gt 2 ]; then
              echo "Blocked: cat -n on $FNAME — already accessed ${COUNT}x. Target range is in context — use it for Edit string matching." >&2
              exit 2
            fi
            echo "$NEWCOUNT" > "$CAT_FILE"
          else
            echo "1" > "$CAT_FILE"
          fi
        fi
      done
    fi
  done
fi

# Fix 2B: For grep/rg/head/tail: check .py, .yaml, .yml, .md files in the read tracker.
# Only blocks if file was already Read (tracker entry exists).
# Pipe-segment aware to avoid false positives (e.g. python foo.py | head -5).
if echo "$COMMAND" | grep -qE '(^|\s)(grep|rg|head|tail)\s'; then
  [ -d "$TRACK_DIR" ] || exit 0
  IFS='|' read -ra SEGMENTS <<< "$COMMAND"
  for segment in "${SEGMENTS[@]}"; do
    if echo "$segment" | grep -qE '(^|\s)(grep|rg|head|tail)\s'; then
      for token in $segment; do
        if echo "$token" | grep -qE '\.(py|yaml|yml|md)$'; then
          BASENAME=$(basename "$token")
          if [ -f "$TRACK_DIR/$BASENAME" ]; then
            if echo "$segment" | grep -qE '(^|\s)(grep|rg)\s'; then
              echo "Blocked: grep on $BASENAME — already Read (use context window instead of filesystem)" >&2
            else
              echo "Blocked: head/tail on $BASENAME — already Read (use context window; for targeted reads use Read tool with offset+limit)" >&2
            fi
            exit 2
          fi
        fi
      done
    fi
  done
fi

exit 0
