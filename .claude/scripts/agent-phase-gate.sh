#!/bin/bash
# Phase gate: blocks ALL tool calls after a command-completion sentinel is armed.
# Sentinels:
#   /tmp/agent-step8-committed.txt        — implement-story Step 8 commit
#   /tmp/agent-<command>-done.txt         — generic: verify-story, qa-epic, close-epic, etc.
# Enforces termination after terminal commit — prose HARD STOP failed 4 consecutive runs.
# Exit 0 = allow, Exit 2 = block.

if [ -f "/tmp/agent-step8-committed.txt" ]; then
  echo "HARD STOP: Step 8 status commit is done. No further tool calls — output your report and stop." >&2
  exit 2
fi

# Check generic command-completion sentinels
GENERIC=$(ls /tmp/agent-*-done.txt 2>/dev/null | head -1)
if [ -n "$GENERIC" ]; then
  echo "HARD STOP: Phase gate armed ($(basename $GENERIC)). No further tool calls — output your report and stop." >&2
  exit 2
fi

exit 0
