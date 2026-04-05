#!/usr/bin/env zsh
# Liquidity Sweep Trial — Golden Strategy Runner
# Working directory: /Users/will/ClaudeProjects/QuantWorkstation

set -e  # exit on error

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
python research/trials/futures/liquidity_sweep/golden.py

record_artifact \
	"research/trials/futures/liquidity_sweep/golden_results.csv" \
	"baseline_csv" \
	"research/trials/futures/liquidity_sweep/golden.py"

echo ""
echo "✓ Golden strategy complete. Review:"
echo "  - research/trials/futures/liquidity_sweep/golden.html"
echo "  - research/trials/futures/liquidity_sweep/golden_results.csv"
echo ""
echo "Documentation:"
echo "  - research/trials/futures/liquidity_sweep/README.md"
echo ""
