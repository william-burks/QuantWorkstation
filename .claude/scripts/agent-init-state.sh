#!/usr/bin/env bash
# Usage: agent-init-state.sh <command-name>
# Called by agents at Step 0 to initialize temp state.
# Clears stale trackers, builds symbol/schema indices, arms command sentinel.
# Idempotent — safe to call on cold start or re-run.
#
# <command-name> is written to /tmp/agent-current-command.txt so guard scripts
# know which command is running. Defaults to "implement-story".

COMMAND="${1:-implement-story}"

# Clear guard trackers
rm -f /tmp/agent-read-tracker/* 2>/dev/null; mkdir -p /tmp/agent-read-tracker
rm -f /tmp/agent-discovery-tracker/* 2>/dev/null; mkdir -p /tmp/agent-discovery-tracker
rm -f /tmp/circuit-breaker/* 2>/dev/null; mkdir -p /tmp/circuit-breaker
# GATE: refuse to clear phase-gate sentinel if it is already armed
if [ -f "/tmp/agent-step8-committed.txt" ]; then
  echo "ERROR: Phase gate is armed (Step 8 committed). Cannot re-initialize. Agent must STOP." >&2
  exit 1
fi

# Build symbol index (functions + classes across graph module)
grep -rn 'def \|class ' qws_graph/research/graph/*.py 2>/dev/null > /tmp/symbol-index.txt || true

# Build schema index (node/edge names from data dictionary)
grep -n '^nodes:\|^relationships:\|^  [A-Z][A-Za-z_]*:' qws_graph/docs/data_dictionary.yaml 2>/dev/null > /tmp/schema-index.txt || true

# Arm command sentinel (activates guard scripts for this command)
echo "$COMMAND" > /tmp/agent-current-command.txt

echo "State initialized for $COMMAND"