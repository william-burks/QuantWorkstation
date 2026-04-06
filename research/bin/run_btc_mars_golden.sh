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

CSV_DIR=research/results/crypto/mars/runs/$(date +%Y%m%d-%H%M%S)
mkdir -p "$CSV_DIR"
CSV="$CSV_DIR/btc_bull_mars_1d_golden_results.csv"
CHAMPION_MD="$CSV_DIR/btc_bull_mars_1d_golden_champion.md"
HTML="$CSV_DIR/btc_bull_mars_1d_golden_report.html"

python research/trials/crypto/mars/golden.py --output-dir "$CSV_DIR"

cat > "$CSV_DIR/bundle.json" <<EOF
{
  "trial": "btc_bull_mars_1d_golden",
  "run_ts": "$(basename $CSV_DIR)",
  "files": {
    "csv": "btc_bull_mars_1d_golden_results.csv",
    "csv_kind": "baseline_csv",
    "html": "btc_bull_mars_1d_golden.html",
    "champion_md": "btc_bull_mars_1d_golden_champion.md"
  }
}
EOF

echo "Bundle manifest written: $CSV_DIR/bundle.json"

qw record --bundle "$CSV_DIR"

echo ""
echo "=== Done ==="
echo ""
echo "Query:"
echo "  qw query --name run_history --param strategy_id=btc-1d-bull-mars"
echo "  qw query --name rank_by_evidence --param strategy_id=btc-1d-bull-mars"
echo "  qw query --name trace_champion --param champion_id=<id from recent_champions>"
