#!/usr/bin/env zsh
# Liquidity Sweep Trial — Position Sizing Runner
# Working directory: /Users/will/ClaudeProjects/QuantWorkstation

set -e  # exit on error

# Source graph environment variables from qws_graph/.env.
# Falls back silently if the file does not exist (allows CI override via exports).
_QWS_ENV_FILE="${0:A:h:h}/qws_graph/.env"
if [[ -f "$_QWS_ENV_FILE" ]]; then
  set -o allexport
  source "$_QWS_ENV_FILE"
  set +o allexport
fi
unset _QWS_ENV_FILE

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

echo "=== Liquidity Sweep Trial — Position Sizing Execution ==="
echo ""

echo "Running liquidity sweep position sizing..."
python research/trials/futures/liquidity_sweep/02_position_sizing.py

record_artifact \
	"research/trials/futures/liquidity_sweep/position_sizing_grid_graph.csv" \
	"grid_csv" \
	"research/trials/futures/liquidity_sweep/02_position_sizing.py"

echo ""
echo "✓ Position sizing complete. Review:"
echo "  - research/trials/futures/liquidity_sweep/position_sizing.html"
echo "  - research/trials/futures/liquidity_sweep/position_sizing_results.csv"
echo "  - research/trials/futures/liquidity_sweep/position_sizing_grid_graph.csv"
echo ""
echo "Documentation:"
echo "  - research/trials/futures/liquidity_sweep/README.md"
echo ""
