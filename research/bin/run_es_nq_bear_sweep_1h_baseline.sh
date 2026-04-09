#!/usr/bin/env zsh
# ES/NQ Bear Sweep Research — Baseline Runner

set -e

source "${0:A:h}/_qws_env.sh"

echo "=== ES/NQ Bear Sweep Research — Phase 1 Execution ==="
echo ""

# Phase 1: Baseline Runs
echo "Phase 1: Running baselines..."
echo ""

echo "Running ES baseline..."
python strategies/legacy/bear_es_sweep_1h_baseline.py
record_artifact "results/es_bear_sweep_1h_baseline.csv" "baseline_csv" "strategies/legacy/bear_es_sweep_1h_baseline.py"

echo ""
echo "Running NQ baseline..."
python strategies/legacy/bear_nq_sweep_1h_baseline.py
record_artifact "results/nq_bear_sweep_1h_baseline.csv" "baseline_csv" "strategies/legacy/bear_nq_sweep_1h_baseline.py"

echo ""
echo "✓ Baselines complete. Review reports in:"
echo "  - results/es_bear_sweep_1h_baseline.csv"
echo "  - results/nq_bear_sweep_1h_baseline.csv"
echo ""

# Phase 2: Isolation (if needed)
# Uncomment below if baseline shows win_rate < breakeven but n >= 20

# echo "Phase 2: Session isolation for ES..."
# python strategies/legacy/bear_es_sweep_1h_baseline.py --allowed-sessions "NY_PRE"
# python strategies/legacy/bear_es_sweep_1h_baseline.py --allowed-sessions "LONDON"
# python strategies/legacy/bear_es_sweep_1h_baseline.py --allowed-sessions "AFTER"
# python strategies/legacy/bear_es_sweep_1h_baseline.py --allowed-sessions "NY_PRE,AFTER"

# Phase 3: Grid Search (if baseline passes gate)
# Uncomment below and adjust parameters based on Phase 2 findings

# echo "Phase 3: Grid search for ES..."
# python strategies/legacy/bear_es_sweep_1h_baseline.py --grid \
#   --target-r-grid "1.0,1.25,1.5,1.75" \
#   --wick-modes "none,exclude_q2,q3_q4_only" \
#   --atr-mult-stop-grid "0.3,0.5,0.7" \
#   --allowed-sessions "NY_PRE,AFTER" \
#   --results-csv "results/es_bear_sweep_1h_grid_v1.csv"

# echo "Phase 3: Grid search for NQ..."
# python strategies/legacy/bear_nq_sweep_1h_baseline.py --grid \
#   --target-r-grid "1.0,1.25,1.5,1.75" \
#   --wick-modes "none,exclude_q2,q3_q4_only" \
#   --atr-mult-stop-grid "0.3,0.5,0.7" \
#   --allowed-sessions "NY_PRE,AFTER" \
#   --results-csv "results/nq_bear_sweep_1h_grid_v1.csv"

echo ""
echo "=== Next Steps ==="
echo "1. Review baseline reports and session/wick breakdowns"
echo "2. Update research/docs/futures/es_nq_bear_sweep_tracker.md with results"
echo "3. If win_rate < breakeven, run Phase 2 isolation (uncomment above)"
echo "4. If baseline passes, run Phase 3 grid search (uncomment above)"
echo ""
echo "Documentation:"
echo "  - Phase 1 guide: research/docs/futures/es_nq_bear_sweep_phase1_plan.md"
echo "  - Master tracker: research/docs/futures/es_nq_bear_sweep_tracker.md"
echo "  - SOP reference: docs/IS_RESEARCH_SOP.md"
echo ""
