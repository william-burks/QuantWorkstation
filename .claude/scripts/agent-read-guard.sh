#!/bin/bash
# Guard script for lead-engineer Read PreToolUse hook.
# Blocks reading out-of-scope command files and limits re-reads of source files.
# Exit 0 = allow, Exit 2 = block (with reason on stderr).

# Only enforce inside a lead-engineer run (implement-story / verify-story / close-story).
# Main session never sets this sentinel, so guards are a no-op outside subagents.
if [ ! -f "/tmp/agent-current-command.txt" ]; then
  exit 0
fi

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[ -z "$FILE" ] && exit 0

# Fix 8B: /tmp/*.py reads count against original source file's tracker (cp/snapshot bypass).
# e.g., /tmp/store_snapshot.py → check tracker for store.py
if echo "$FILE" | grep -qE '^/tmp/.*\.(py|yaml|yml|md)$'; then
  TMP_BASENAME=$(basename "$FILE")
  TRACK_DIR_EARLY="/tmp/agent-read-tracker"
  if [ -d "$TRACK_DIR_EARLY" ]; then
    ORIG=$(echo "$TMP_BASENAME" | sed -E 's/_(snapshot|backup|copy|orig|tmp)[0-9]*\.[^.]+$//' | sed -E 's/_(snapshot|backup|copy|orig|tmp)[0-9]*$//' | sed -E 's/\.[^.]+$//')
    ORIG_PY="${ORIG}.py"
    ORIG_YML="${ORIG}.yaml"
    for ORIG_NAME in "$ORIG_PY" "$ORIG_YML" "$TMP_BASENAME"; do
      if [ -f "$TRACK_DIR_EARLY/$ORIG_NAME" ]; then
        COUNT=$(cat "$TRACK_DIR_EARLY/$ORIG_NAME")
        if [ "$COUNT" -ge 2 ]; then
          echo "Blocked: $TMP_BASENAME appears to be a /tmp/ snapshot of $ORIG_NAME (already read ${COUNT}x) — use context" >&2
          exit 2
        fi
        NEWCOUNT=$((COUNT + 1))
        echo "$NEWCOUNT" > "$TRACK_DIR_EARLY/$ORIG_NAME"
        exit 0
      fi
    done
  fi
  exit 0
fi

# Block reading out-of-scope command files during implement-story.
if echo "$FILE" | grep -qE '\.claude/commands/close-story\.md$'; then
  echo "Blocked: lead-engineer cannot read close-story.md — orchestrator spawns close as a separate agent" >&2
  exit 2
fi
# Fix 6: Block verify-story.md pre-read during implement-story (breadcrumb set in Step 0).
if echo "$FILE" | grep -qE '\.claude/commands/verify-story\.md$'; then
  if [ -f "/tmp/agent-current-command.txt" ] && grep -q "implement-story" /tmp/agent-current-command.txt 2>/dev/null; then
    echo "Blocked: do not pre-read verify-story.md during implement-story — orchestrator invokes it separately after implementation" >&2
    exit 2
  fi
fi

# Track and limit re-reads of source files.
# Uses /tmp/agent-read-tracker/ — reset by implement-story.md Step 0.
TRACK_DIR="/tmp/agent-read-tracker"
mkdir -p "$TRACK_DIR" 2>/dev/null || true

# Normalize to basename for tracking (unique basenames in this project).
BASENAME=$(basename "$FILE")

# Skip tracking for: memory files, test files, docs, command files.
# Track story files (story_*.md) to catch mid-run re-reads.
# Only track implementation source files and story files likely to be re-read wastefully.
# Skip small config files — not re-read wastefully
# Fix 2A: Track .yaml/.yml (data_dictionary.yaml re-read 4x in R8)
if echo "$BASENAME" | grep -qE '\.(json|cfg|txt)$'; then
  exit 0
fi
# Track .toml files (pyproject.toml re-grepped 5x in R10 after not being read)
# Falls through to standard read-count tracking below.
# For .md files: track those inside qws_graph/ (implementation docs like graph_v1_contract.md
# that shouldn't change mid-run). Exempt .md outside qws_graph/ (command files, project docs).
if echo "$BASENAME" | grep -qE '\.md$'; then
  # Always track story_*.md (mid-run re-reads)
  if echo "$BASENAME" | grep -qE '^story_'; then
    : # fall through to tracking
  # INDEX.md is a registry file legitimately read many times during refine-epic/close-epic — never cap it.
  elif echo "$BASENAME" | grep -qE '^INDEX\.md$'; then
    exit 0
  # Track qws_graph/ .md files (e.g. graph_v1_contract.md, data_dictionary content)
  elif echo "$FILE" | grep -qE 'qws_graph/'; then
    : # fall through to tracking
  else
    exit 0
  fi
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
