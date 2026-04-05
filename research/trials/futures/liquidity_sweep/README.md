# Liquidity Sweep Trial

This trial runs `bear_nypre_after_1h_no_smt_exclude_q2_v2.py` logic through
`strategies.adapters.liquidity_sweep_adapter` using ArcticDB symbols:

- `CL_continuous_5min`
- `CL_continuous_1H`
- `MES_continuous_5min`
- `MNQ_continuous_5min`

## Baseline run

```bash
python research/trials/futures/liquidity_sweep/01_baseline.py
```

Graph-enabled runner (same `qw record` plumbing pattern as other research scripts):

```bash
./research/run_liquidity_sweep_baseline.sh
```

The baseline config in `01_baseline.py` follows the explained profile:
`BEAR` + `NY_PRE/AFTER`, `exclude_q2`, no SMT in chain, `target_r=1.25`,
`max_hold_bars=24`, no partial/stall exits.

Baseline artifacts written to this folder:

- `index.html`
- `baseline_results.csv`

## Position sizing comparison

```bash
python research/trials/futures/liquidity_sweep/02_position_sizing.py
```

Graph-enabled runner:

```bash
./research/run_liquidity_sweep_position_sizing.sh
```

This replays the same baseline trades under multiple risk rules (fixed risk,
drawdown throttle, loss-streak throttle, and `r_dist` volatility targeting).

Artifacts written to this folder:

- `position_sizing_results.csv`
- `position_sizing_equity_curves.csv`
- `position_sizing_summary.json`
- `position_sizing.html`
- `position_sizing_grid_graph.csv`

## Golden strategy (rdist volatility targeting)

```bash
python research/trials/futures/liquidity_sweep/golden.py
```

Graph-enabled runner:

```bash
./research/run_liquidity_sweep_golden.sh
```

The golden strategy applies optimized position sizing based on reward-to-risk distance scaling,
using the baseline entry/exit rules with enhanced risk management.

Golden strategy artifacts written to this folder:

- `golden.html`
- `golden_results.csv`
