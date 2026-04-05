#!/usr/bin/env zsh
# BTC Bull MARS 1D Golden Strategy — run backtest and ingest to graph.
# Usage: ./research/bin/run_btc_mars_golden.sh

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

CSV=research/results/crypto/mars/btc_bull_mars_1d_golden_results.csv
CHAMPION_MD=research/results/crypto/mars/btc_bull_mars_1d_golden_champion.md

echo "=== BTC Bull MARS 1D Golden ==="
echo ""

python research/trials/crypto/mars/golden.py

echo ""
echo "--- Graph ingest ---"

if [[ -f "$CSV" ]]; then
  qw record --file "$CSV" --kind baseline_csv || true
else
  echo "WARNING: CSV not found — skipping baseline_csv ingest"
fi

if [[ -f "$CHAMPION_MD" ]]; then
  qw record --file "$CHAMPION_MD" --kind champion_md || true
else
  echo "WARNING: Champion MD not found — skipping champion_md ingest"
fi

echo ""
echo "=== Done ==="
echo ""
echo "Query:"
echo "  qw query --name run_history --param strategy_id=btc-1d-bull-mars"
echo "  qw query --name rank_by_evidence --param strategy_id=btc-1d-bull-mars"
echo "  qw query --name trace_champion --param champion_id=<id from recent_champions>"
