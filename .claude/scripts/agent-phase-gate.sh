#!/bin/bash
# Phase gate: blocks ALL tool calls after Step 8 commit sentinel is set.
# Sentinel: /tmp/agent-step8-committed.txt (written by implement-story.md Step 8).
# Enforces termination after READY → TESTING commit — prose HARD STOP failed 4 consecutive runs.
# Exit 0 = allow, Exit 2 = block.

if [ -f "/tmp/agent-step8-committed.txt" ]; then
  echo "HARD STOP: Step 8 status commit is done. No further tool calls — output your report and stop." >&2
  exit 2
fi

exit 0
