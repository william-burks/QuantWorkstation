#!/usr/bin/env zsh
# Liquidity Sweep Trial — Golden Strategy Runner

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

RUN_TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="research/results/futures/liquidity_sweep/runs/${RUN_TS}"
mkdir -p "${RUN_DIR}"
echo "Run directory: ${RUN_DIR}"

record_artifact() {
	local artifact_file="$1"
	local artifact_kind="$2"
	local source_file="${3:-}"

	# Python CSV writes may still be buffered when the process exits.
	sleep 1

	if [[ ! -f "$artifact_file" ]]; then
		echo "WARNING: expected artifact not found for graph hook: $artifact_file" >&2
		return
	fi

	local source_flag=()
	if [[ -n "$source_file" ]]; then
		source_flag=(--source-file "$source_file")
	fi

	if [[ "${QW_GRAPH_ENABLED:-true}" == "false" ]]; then
		qw record --file "$artifact_file" --kind "$artifact_kind" "${source_flag[@]}" --offline || true
		return
	fi

	qw record --file "$artifact_file" --kind "$artifact_kind" "${source_flag[@]}" || true
}

echo "=== Liquidity Sweep Trial — Golden Strategy Execution ==="
echo ""

echo "Running liquidity sweep golden strategy..."
python research/trials/futures/liquidity_sweep/golden.py --output-dir "${RUN_DIR}"

cat > "${RUN_DIR}/bundle.json" <<EOF
{
  "trial": "liquidity_sweep_golden",
  "run_ts": "${RUN_TS}",
  "files": {
    "csv": "golden_results.csv",
    "csv_kind": "baseline_csv",
    "html": "golden.html"
  }
}
EOF

echo "Bundle manifest written: ${RUN_DIR}/bundle.json"

if [[ "${QW_GRAPH_ENABLED:-true}" == "false" ]]; then
	echo "INFO: QW_GRAPH_ENABLED=false — skipping graph ingest"
else
	qw record --bundle "${RUN_DIR}" || true
fi

# Champion markdown is co-located in RUN_DIR but not part of the bundle manifest.
# Record it separately via --file mode.
record_artifact \
	"${RUN_DIR}/cl_bear_liquidity_sweep_1h_golden_champion.md" \
	"champion_md" \
	"research/trials/futures/liquidity_sweep/golden.py"

echo ""
echo "✓ Golden strategy complete. Review:"
echo "  - ${RUN_DIR}/golden.html"
echo "  - ${RUN_DIR}/golden_results.csv"
echo "  - ${RUN_DIR}/cl_bear_liquidity_sweep_1h_golden_champion.md"
echo ""
echo "Documentation:"
echo "  - research/trials/futures/liquidity_sweep/README.md"
echo ""
