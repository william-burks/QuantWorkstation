#!/usr/bin/env bash
# Usage: locate-story.sh QWS-NNNN [--closed]
# Prints the absolute path to the story file for the given ID.
# Searches open stories by default; pass --closed to search closed/ subdirectories.
# Exits 1 if not found.

set -uo pipefail

STORY_ID="${1:-}"
CLOSED="${2:-}"

if [[ -z "$STORY_ID" ]]; then
    echo "Usage: locate-story.sh QWS-NNNN [--closed]" >&2
    exit 1
fi

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
EPICS_DIR="$REPO_ROOT/qws_graph/epics"

# Primary: story ID in filename (most reliable — avoids README/INDEX false matches)
if [[ "$CLOSED" == "--closed" ]]; then
    RESULT=$(find "$EPICS_DIR" -name "${STORY_ID}*.md" 2>/dev/null | head -1)
else
    RESULT=$(find "$EPICS_DIR" -name "${STORY_ID}*.md" 2>/dev/null \
        | grep -v '/closed/' | head -1)
fi

# Secondary: standalone ID on its own line in file content
if [[ -z "$RESULT" ]]; then
    if [[ "$CLOSED" == "--closed" ]]; then
        RESULT=$(grep -rl "^${STORY_ID}$" "$EPICS_DIR" 2>/dev/null | head -1)
    else
        RESULT=$(grep -rl "^${STORY_ID}$" "$EPICS_DIR" 2>/dev/null \
            | grep -v '/closed/' | head -1)
    fi
fi

# Tertiary: ID anywhere in file (README/INDEX excluded by name to avoid false matches)
if [[ -z "$RESULT" ]]; then
    if [[ "$CLOSED" == "--closed" ]]; then
        RESULT=$(grep -rl "$STORY_ID" "$EPICS_DIR" 2>/dev/null \
            | grep -v '/README\.md\|/INDEX\.md' | head -1)
    else
        RESULT=$(grep -rl "$STORY_ID" "$EPICS_DIR" 2>/dev/null \
            | grep -v '/closed/' | grep -v '/README\.md\|/INDEX\.md' | head -1)
    fi
fi

if [[ -z "$RESULT" ]]; then
    echo "Story $STORY_ID not found" >&2
    exit 1
fi

echo "$RESULT"
