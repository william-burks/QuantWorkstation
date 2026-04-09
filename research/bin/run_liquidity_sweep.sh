#!/usr/bin/env zsh
# Liquidity Sweep Trial Runner
# Usage: ./research/bin/run_liquidity_sweep.sh <trial_script>
# Examples:
#   ./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/baseline.py
#   ./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/golden.py
#   ./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/02_position_sizing.py

set -e

TRIAL_SCRIPT="${1:?Usage: $0 <trial_script>}"

source "${0:A:h}/_qws_env.sh"

RUN_TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="research/results/futures/liquidity_sweep/runs/${RUN_TS}"
mkdir -p "${RUN_DIR}"
echo "Run directory: ${RUN_DIR}"
echo "Trial: ${TRIAL_SCRIPT}"
echo ""

python "${TRIAL_SCRIPT}" --output-dir "${RUN_DIR}"

sleep 1  # flush buffered writes

if [[ "${QW_GRAPH_ENABLED:-true}" == "false" ]]; then
  echo "INFO: QW_GRAPH_ENABLED=false — skipping graph ingest"
else
  qw record --bundle "${RUN_DIR}" || true
  # Record champion markdown if present (written by golden.py)
  for md in "${RUN_DIR}"/*_champion.md; do
    [[ -f "$md" ]] && qw record --file "$md" --kind "champion_md" --source-file "${TRIAL_SCRIPT}" || true
  done
fi

echo ""
echo "Done. Run artifacts: ${RUN_DIR}"
echo "Documentation: research/trials/futures/liquidity_sweep/README.md"
