#!/usr/bin/env bash
# Usage: set-story-status.sh QWS-NNNN NEW_STATUS [--closed]
# Updates status in three files:
#   1. Story file — ## Status field
#   2. qws_graph/epics/INDEX.md — trailing `STATUS` on the story's line
#   3. docs/BACKLOG_ALIGNMENT.md — QWS-NNNN (**STATUS**) inline in the ID column
# Pass --closed if the story lives in a closed/ subdirectory.
# NOTE: BACKLOG_ALIGNMENT.md "Blocked On" strikethrough for OTHER stories is NOT
#       handled here — that requires agent judgment.
# Exits 1 if story not found or status invalid.

set -euo pipefail

STORY_ID="${1:-}"
NEW_STATUS="${2:-}"
CLOSED="${3:-}"

VALID_STATUSES="READY BLOCKED IN_PROGRESS TESTING CLOSED"

usage() {
    echo "Usage: set-story-status.sh QWS-NNNN NEW_STATUS [--closed]" >&2
    echo "Valid statuses: $VALID_STATUSES" >&2
    exit 1
}

if [[ -z "$STORY_ID" || -z "$NEW_STATUS" ]]; then
    usage
fi

# Validate status
VALID=0
for s in $VALID_STATUSES; do
    if [[ "$NEW_STATUS" == "$s" ]]; then
        VALID=1
        break
    fi
done
if [[ $VALID -eq 0 ]]; then
    echo "Invalid status: $NEW_STATUS" >&2
    echo "Valid statuses: $VALID_STATUSES" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

STORY_FILE=$("$SCRIPT_DIR/locate-story.sh" "$STORY_ID" $CLOSED)
if [[ -z "$STORY_FILE" ]]; then
    exit 1
fi

# --- 1. Story file: replace line after "## Status" ---
CURRENT=$(awk '/^## Status/{found=1; next} found && NF{print; exit}' "$STORY_FILE")

awk -v new="$NEW_STATUS" '
    /^## Status/ { in_status=1; print; next }
    in_status && NF { print new; in_status=0; next }
    in_status && !NF { print; next }
    { print }
' "$STORY_FILE" > "${STORY_FILE}.tmp" && mv "${STORY_FILE}.tmp" "$STORY_FILE"

echo "story:   $STORY_ID $CURRENT → $NEW_STATUS"

# --- 2. INDEX.md: update trailing `STATUS` on the story's line ---
INDEX="$REPO_ROOT/qws_graph/epics/INDEX.md"
if [[ -f "$INDEX" ]]; then
    # Find line containing story ID, replace — `any_status` with new status
    sed -i.bak "/${STORY_ID}/s/— \`[a-zA-Z_]*\`/— \`${NEW_STATUS}\`/" "$INDEX" && rm -f "${INDEX}.bak"
    echo "index:   updated"
else
    echo "index:   not found (skipped)"
fi

# --- 3. BACKLOG_ALIGNMENT.md: update (**STATUS**) in the ID column ---
BACKLOG="$REPO_ROOT/docs/BACKLOG_ALIGNMENT.md"
if [[ -f "$BACKLOG" ]]; then
    sed -i.bak "s/${STORY_ID} (\*\*[A-Z_]*\*\*)/${STORY_ID} (\*\*${NEW_STATUS}\*\*)/" "$BACKLOG" && rm -f "${BACKLOG}.bak"
    echo "backlog: updated"
else
    echo "backlog: not found (skipped)"
fi