# Liquidity Sweep Trial

This trial runs `strategies/bear_cl_sweep_1h_baseline.py` logic through
`strategies.adapters.liquidity_sweep_adapter` using ArcticDB symbols:

- `CL_continuous_5min`
- `CL_continuous_1H`
- `MES_continuous_5min`
- `MNQ_continuous_5min`

## Running trials

All trials share a single runner. Pass the trial script as the first argument:

```bash
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/baseline.py
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/golden.py
./research/bin/run_liquidity_sweep.sh research/trials/futures/liquidity_sweep/02_position_sizing.py
```

Each run writes artifacts to a timestamped directory under
`research/results/futures/liquidity_sweep/runs/<YYYYMMDD-HHMMSS>/`
and ingests them into the graph via `qw record`.

---

## Baseline (`baseline.py`)

The baseline config follows the explained profile:
`BEAR` + `NY_PRE/AFTER`, `exclude_q2`, no SMT in chain, `target_r=1.25`,
`max_hold_bars=24`, no partial/stall exits.

Artifacts:

- `index.html`
- `baseline_results.csv`

## Position sizing comparison (`02_position_sizing.py`)

Replays the same baseline trades under multiple risk rules (fixed risk,
drawdown throttle, loss-streak throttle, and `r_dist` volatility targeting).

Artifacts:

- `position_sizing_results.csv`
- `position_sizing_equity_curves.csv`
- `position_sizing_summary.json`
- `position_sizing.html`
- `position_sizing_grid_graph.csv`

## Golden strategy (`golden.py`)

Applies the optimized `rdist_vol_target` position sizing on top of the
baseline entry/exit rules.

Artifacts:

- `golden.html`
- `golden_results.csv`
- `cl_bear_liquidity_sweep_1h_golden_champion.md`
