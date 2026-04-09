#!/usr/bin/env zsh
# Run all research phases 1-9 in sequence
set -e

# Phase 1-3: ES/NQ Bear Sweep (Phase 2 script covers 1-3)
echo "=== PHASE 1-3: ES/NQ Bear Sweep Isolation ==="
./research/bin/run_es_phase2.sh all

echo "=== PHASE 4: Liquidity Sweep Baseline ==="
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/baseline.py

echo "=== PHASE 5: Liquidity Sweep Position Sizing ==="
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/02_position_sizing.py

echo "=== PHASE 6: Liquidity Sweep Golden ==="
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/golden.py

echo "=== PHASE 7: BTC Mars Golden ==="
./research/bin/run_btc_mars_golden.sh

# Add additional phases here as new scripts are available
# echo "=== PHASE 8: ... ==="
# ./research/bin/run_phase8.sh
# echo "=== PHASE 9: ... ==="
# ./research/bin/run_phase9.sh

echo "=== ALL PHASES COMPLETE ==="

