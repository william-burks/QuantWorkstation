#!/usr/bin/env zsh
# ES Phase 2 Isolation — Quick Runner
# Usage: ./run_es_phase2.sh [1a|1b|2a|2b|3a|3b|nq]
# Or: ./run_es_phase2.sh all (runs all in sequence)

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

# Create results dir if needed
mkdir -p results

record_artifact() {
    local artifact_file="$1"
    local artifact_kind="$2"

    # Python CSV writes may still be buffered when the process exits; give the
    # filesystem a moment to sync before checking for the artifact.
    sleep 1

    if [[ ! -f "$artifact_file" ]]; then
        echo "WARNING: expected artifact not found for graph hook: $artifact_file" >&2
        return
    fi

    if [[ "${QW_GRAPH_ENABLED:-true}" == "false" ]]; then
        qw record --file "$artifact_file" --kind "$artifact_kind" --offline || true
        return
    fi

    qw record --file "$artifact_file" --kind "$artifact_kind" || true
}

# Logging function
log_test() {
    local test_id=$1
    local desc=$2
    local cmd=$3

    echo ""
    echo "=========================================="
    echo "TEST $test_id — $desc"
    echo "=========================================="
    echo "Running: $cmd"
    echo ""

    eval "$cmd"

    echo ""
    echo "✓ $test_id complete. Log result in tracker."
    echo ""
}

# ES Test 1A: NY_PRE Only
test_1a() {
    log_test "1A" "ES: NY_PRE Only" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE' \
            --results-csv 'results/es_bear_sweep_1h_nypre.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre.csv" "baseline_csv"
}

# ES Test 1B: NY_PRE + LONDON
test_1b() {
    log_test "1B" "ES: NY_PRE + LONDON" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE,LONDON' \
            --results-csv 'results/es_bear_sweep_1h_nypre_london.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre_london.csv" "baseline_csv"
}

# ES Test 2A: Exclude Q2 Wicks (within NY_PRE)
test_2a() {
    log_test "2A" "ES: NY_PRE + exclude_q2 wicks" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE' \
            --wick-mode 'exclude_q2' \
            --results-csv 'results/es_bear_sweep_1h_nypre_excq2.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre_excq2.csv" "baseline_csv"
}

# ES Test 2B: Q3+Q4 Only (within NY_PRE)
test_2b() {
    log_test "2B" "ES: NY_PRE + q3_q4_only wicks" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE' \
            --wick-mode 'q3_q4_only' \
            --results-csv 'results/es_bear_sweep_1h_nypre_q3q4.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre_q3q4.csv" "baseline_csv"
}

# ES Test 3A: Tighter Stop (0.3 ATR)
test_3a() {
    log_test "3A" "ES: NY_PRE + exclude_q2 + 0.3 ATR stop" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE' \
            --wick-mode 'exclude_q2' \
            --atr-mult-stop 0.3 \
            --results-csv 'results/es_bear_sweep_1h_nypre_excq2_atr03.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre_excq2_atr03.csv" "baseline_csv"
}

# ES Test 3B: Looser Stop (0.7 ATR)
test_3b() {
    log_test "3B" "ES: NY_PRE + exclude_q2 + 0.7 ATR stop" \
        "python strategies/legacy/bear_es_sweep_1h_baseline.py \
            --allowed-sessions 'NY_PRE' \
            --wick-mode 'exclude_q2' \
            --atr-mult-stop 0.7 \
            --results-csv 'results/es_bear_sweep_1h_nypre_excq2_atr07.csv'"
    record_artifact "results/es_bear_sweep_1h_nypre_excq2_atr07.csv" "baseline_csv"
}

# NQ Test: ASIA Only
test_nq() {
    log_test "NQ" "NQ: ASIA Only (quick probe)" \
        "python strategies/legacy/bear_nq_sweep_1h_baseline.py \
            --allowed-sessions 'ASIA' \
            --results-csv 'results/nq_bear_sweep_1h_asia.csv'"
    record_artifact "results/nq_bear_sweep_1h_asia.csv" "baseline_csv"
}

# Run all tests in sequence
run_all() {
    echo "Running full ES Phase 2 isolation sequence..."
    test_1a
    test_1b
    test_2a
    test_2b
    test_3a
    echo ""
    echo "=========================================="
    echo "✓ All ES isolation tests complete."
    echo "Review results in results/ and update tracker."
    echo "=========================================="
}

# Main
case "${1:-all}" in
    1a) test_1a ;;
    1b) test_1b ;;
    2a) test_2a ;;
    2b) test_2b ;;
    3a) test_3a ;;
    3b) test_3b ;;
    nq) test_nq ;;
    all) run_all ;;
    *)
        echo "Usage: $0 [1a|1b|2a|2b|3a|3b|nq|all]"
        echo ""
        echo "Tests:"
        echo "  1a  — ES: NY_PRE only"
        echo "  1b  — ES: NY_PRE + LONDON"
        echo "  2a  — ES: NY_PRE + exclude Q2"
        echo "  2b  — ES: NY_PRE + Q3/Q4 only"
        echo "  3a  — ES: NY_PRE + exclude Q2 + 0.3 ATR"
        echo "  3b  — ES: NY_PRE + exclude Q2 + 0.7 ATR"
        echo "  nq  — NQ: ASIA only (quick probe)"
        echo "  all — Run 1a, 1b, 2a, 2b, 3a in sequence (default)"
        exit 1
        ;;
esac

