#!/usr/bin/env zsh
# Graph integrity QA — validates structural invariants, not expected metric values.
# Usage: ./research/bin/qa_graph_integrity.sh
# Requires: qw CLI on PATH, jq installed, Neo4j running with qws_graph/.env credentials.

set -e

_QWS_ROOT="$(git -C "${0:A:h}" rev-parse --show-toplevel 2>/dev/null || echo "${0:A:h:h:h}")"
_QWS_ENV_FILE="$_QWS_ROOT/qws_graph/.env"
if [[ -f "$_QWS_ENV_FILE" ]]; then
  set -o allexport
  source "$_QWS_ENV_FILE"
  set +o allexport
fi
unset _QWS_ENV_FILE
cd "$_QWS_ROOT"
unset _QWS_ROOT

PASS=0
FAIL=0

_pass() { echo "[PASS] $1"; (( ++PASS )); }
_fail() { echo "[FAIL] $1"; (( ++FAIL )); }

echo "=== QuantWorkstation Graph Integrity QA ==="
echo ""

# --- Check 1: Graph is reachable and has at least one Champion ---
# Output without --json is NDJSON: one JSON object per line.
echo "Check 1: Graph connectivity and champion presence"
CHAMPIONS=$(qw query --name recent_champions 2>/dev/null) || {
  _fail "Graph unreachable — qw query exited non-zero"
  echo ""
  echo "RESULT: 1 failure (graph unreachable). Remaining checks skipped."
  exit 1
}
COUNT=$(echo "$CHAMPIONS" | jq -s 'length')
if [[ "$COUNT" -ge 1 ]]; then
  _pass "Graph reachable, $COUNT champion(s) present"
else
  _fail "No champions found — graph may be empty or ingestion failed"
fi

# --- Check 2: Flat metrics populated (avg_sharpe not null) ---
echo ""
echo "Check 2: Champion flat metric properties"
ALPHA=$(qw query --name portfolio_alpha 2>/dev/null)
AVG_SHARPE=$(echo "$ALPHA" | jq '.avg_sharpe // null')
if [[ "$AVG_SHARPE" != "null" && -n "$AVG_SHARPE" ]]; then
  _pass "Champion flat metrics present (avg_sharpe=$AVG_SHARPE)"
else
  _fail "avg_sharpe is null — Champion nodes missing flat metrics_* properties (re-ingest required)"
fi

# --- Check 3: Fragility report runs without error ---
echo ""
echo "Check 3: Fragility report"
qw query --name fragility_report > /dev/null 2>&1 && \
  _pass "fragility_report preset executes without error" || \
  _fail "fragility_report preset failed"

# --- Check 4: Trace resolves for the most recent champion ---
echo ""
echo "Check 4: Champion lineage trace"
LATEST_ID=$(echo "$CHAMPIONS" | jq -rs '.[0].champion_id // empty')
if [[ -n "$LATEST_ID" ]]; then
  TRACE=$(qw query --name trace_champion --param "champion_id=$LATEST_ID" 2>/dev/null)
  STRATEGY=$(echo "$TRACE" | jq -r '.strategy_id // empty')
  if [[ -n "$STRATEGY" ]]; then
    _pass "Lineage trace resolved: champion $LATEST_ID → strategy $STRATEGY"
  else
    _fail "trace_champion returned no strategy for champion_id=$LATEST_ID"
  fi
else
  _fail "Could not extract latest champion_id for lineage trace"
fi

# --- Check 5: Champion trade count significance ---
echo ""
echo "Check 5: Champion trade count significance"
if [[ -n "$LATEST_ID" ]]; then
  CHAMPION_TRADES=$(qw query --name trace_champion --param "champion_id=$LATEST_ID" 2>/dev/null | jq -r '.metrics_total_trades // empty')
  if [[ -z "$CHAMPION_TRADES" || "$CHAMPION_TRADES" == "null" ]]; then
    _fail "Champion metrics_total_trades missing — re-ingest champion markdown after golden.py update"
  elif [[ "$CHAMPION_TRADES" -lt 5 ]]; then
    _fail "Champion trade count ($CHAMPION_TRADES) below significance threshold of 5 — evidence is thin"
  else
    _pass "Champion trade count ($CHAMPION_TRADES) meets significance threshold (≥5)"
  fi
else
  _fail "Could not check trade count — champion_id unavailable"
fi

# --- Summary ---
echo ""
echo "=== QA Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo ""

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi

# --- Next Action ---
echo "=== Next Action ==="
LATEST_STRATEGY=$(echo "$CHAMPIONS" | jq -rs '.[0].strategy_id // empty')
LATEST_ARTIFACT=$(echo "$CHAMPIONS" | jq -rs '.[0].artifact_path // empty')
LATEST_FREEZE=$(echo "$CHAMPIONS" | jq -rs '.[0].freeze_date // empty')

if [[ -n "$LATEST_STRATEGY" ]]; then
  echo "  Top champion: $LATEST_ID"
  echo "  Strategy:     $LATEST_STRATEGY"
  echo "  Frozen:       ${LATEST_FREEZE:-unknown}"
  echo ""
  echo "  Run OOS validation:"
  echo "    qw query --name run_history --param strategy_id=$LATEST_STRATEGY"
  echo ""
  if [[ -n "$LATEST_ARTIFACT" ]]; then
    echo "  Champion artifact: $LATEST_ARTIFACT"
  fi
else
  echo "  Could not determine top champion for next action."
fi
