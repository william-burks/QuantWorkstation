#!/bin/bash
# PostToolUse hook: appends one JSONL line per tool call to /tmp/agent-trace-<agent>-<PID>.jsonl
# Reads agent name from /tmp/agent-trace-active.txt (written by orchestrator before spawn).
# No-op if sentinel missing — only traces agents that opted in.
# PID = $PPID (the spawned agent process).

SENTINEL="/tmp/agent-trace-active.txt"
[ ! -f "$SENTINEL" ] && exit 0

AGENT_NAME=$(cat "$SENTINEL" 2>/dev/null)
[ -z "$AGENT_NAME" ] && exit 0

TRACE_FILE="/tmp/agent-trace-${AGENT_NAME}-${PPID}.jsonl"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
# Truncate response to 500 chars to keep trace files manageable
TOOL_RESPONSE=$(echo "$INPUT" | jq -c '.tool_response // ""' | cut -c1-500)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

printf '{"tool":"%s","target":%s,"result":"%s","ts":"%s"}\n' \
  "$TOOL_NAME" "$TOOL_INPUT" "$TOOL_RESPONSE" "$TIMESTAMP" >> "$TRACE_FILE"

exit 0
