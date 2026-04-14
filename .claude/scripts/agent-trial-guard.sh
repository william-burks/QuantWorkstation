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

  # Block qw record --bundle when bundle.json is missing hypothesis_id
  # Pattern: qw record --bundle <dir> → check bundle.json in that dir
  if echo "$COMMAND" | grep -qE 'qw\s+record\s+.*--bundle'; then
    BUNDLE_DIR=$(echo "$COMMAND" | grep -oE '\-\-bundle\s+\S+' | awk '{print $2}')
    if [ -n "$BUNDLE_DIR" ]; then
      BUNDLE_FILE="$BUNDLE_DIR/bundle.json"
      if [ -f "$BUNDLE_FILE" ]; then
        if ! jq -e '.hypothesis_id' "$BUNDLE_FILE" > /dev/null 2>&1; then
          echo "Blocked: bundle.json at $BUNDLE_FILE is missing hypothesis_id — add it before ingesting" >&2
          exit 2
        fi
        HYP_ID=$(jq -r '.hypothesis_id // empty' "$BUNDLE_FILE")
        if [ -z "$HYP_ID" ] || [ "$HYP_ID" = "null" ]; then
          echo "Blocked: bundle.json hypothesis_id is empty or null — set a valid hypothesis_id" >&2
          exit 2
        fi
      else
        echo "Blocked: bundle.json not found at $BUNDLE_FILE — write bundle before ingesting" >&2
        exit 2
      fi
    fi
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

    # Block writes to util/
    if echo "$FILE_PATH" | grep -qE '(^|/)util/'; then
      echo "Blocked: trial-engineer cannot write to util/ — utility scripts are off-limits" >&2
      exit 2
    fi

    # Block trial script writes where proposed NN ≠ max existing NN + 1
    # Pattern: research/trials/<asset>/<strategy>/NN_description.py
    if echo "$FILE_PATH" | grep -qE 'research/trials/[^/]+/[^/]+/[0-9]+_[^/]+\.py$'; then
      PROPOSED_NN=$(basename "$FILE_PATH" | grep -oE '^[0-9]+')
      TRIAL_DIR=$(dirname "$FILE_PATH")
      if [ -d "$TRIAL_DIR" ]; then
        MAX_NN=$(ls "$TRIAL_DIR"/*.py 2>/dev/null | grep -oE '/[0-9]+_' | grep -oE '[0-9]+' | sort -n | tail -1)
        if [ -n "$MAX_NN" ]; then
          EXPECTED_NN=$((MAX_NN + 1))
          # Zero-pad expected to same width as proposed
          PROPOSED_INT=$(echo "$PROPOSED_NN" | sed 's/^0*//')
          if [ -n "$PROPOSED_INT" ] && [ "$PROPOSED_INT" != "$EXPECTED_NN" ]; then
            echo "Blocked: trial NN=$PROPOSED_INT but expected NN=$EXPECTED_NN (max existing=$MAX_NN + 1)" >&2
            exit 2
          fi
        fi
      fi
    fi

    # Block trial script writes where filename does not match NN_description.py
    if echo "$FILE_PATH" | grep -qE 'research/trials/'; then
      BASENAME=$(basename "$FILE_PATH")
      if echo "$BASENAME" | grep -qE '\.py$'; then
        if ! echo "$BASENAME" | grep -qE '^[0-9]+_[a-z0-9_]+\.py$'; then
          echo "Blocked: trial script filename '$BASENAME' does not match NN_description.py pattern" >&2
          exit 2
        fi
      fi
    fi

  fi
fi

exit 0
