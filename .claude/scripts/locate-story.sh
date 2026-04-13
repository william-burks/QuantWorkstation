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

if [[ "$CLOSED" == "--closed" ]]; then
    RESULT=$(grep -rl "^${STORY_ID}$" "$EPICS_DIR" 2>/dev/null | head -1)
else
    # Exclude closed/ subdirectories by default
    RESULT=$(grep -rl "^${STORY_ID}$" "$EPICS_DIR" 2>/dev/null \
        | grep -v '/closed/' | head -1)
fi

if [[ -z "$RESULT" ]]; then
    # Fallback: match ID line as standalone value under ## ID heading
    if [[ "$CLOSED" == "--closed" ]]; then
        RESULT=$(grep -rl "$STORY_ID" "$EPICS_DIR" 2>/dev/null | head -1)
    else
        RESULT=$(grep -rl "$STORY_ID" "$EPICS_DIR" 2>/dev/null \
            | grep -v '/closed/' | head -1)
    fi
fi

if [[ -z "$RESULT" ]]; then
    echo "Story $STORY_ID not found" >&2
    exit 1
fi

echo "$RESULT"
