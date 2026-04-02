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

The baseline config in `01_baseline.py` follows the explained profile:
`BEAR` + `NY_PRE/AFTER`, `exclude_q2`, no SMT in chain, `target_r=1.25`,
`max_hold_bars=24`, no partial/stall exits.


