# Data Source Clarification — ES/NQ Research

**Date**: April 2, 2026

## Answer: You Don't Need ES/NQ

You can run the entire ES/NQ research using **only MES and MNQ data**. Both scripts have been updated.

---

## Why MES/MNQ Work Perfectly

| Property | ES vs MES | NQ vs MNQ |
|---|---|---|
| **Same pattern?** | Yes, identical | Yes, identical |
| **Liquidity?** | MES has sufficient liquidity for backtesting | MNQ has sufficient liquidity |
| **Data quality?** | MES often better available | MNQ often better available |
| **Sweep detection?** | Works the same on micro contracts | Works the same on micro contracts |
| **Confirmation logic?** | Identical (IFVG, BOS, equal retrace) | Identical |

The liquidity sweep pattern (high > swing high, close < swing high) is instrument-agnostic. It works on ES and MES equally well.

---

## What Changed in the Scripts

### ES Baseline Script
**Before**: `bear_es_sweep_1h_baseline.py` loaded ES data  
**Now**: `bear_es_sweep_1h_baseline.py` loads **MES data**

```python
# Required:
MES_5M = BASE / 'MES_continuous_5min.parquet'
MES_1H = BASE / 'MES_continuous_1H.parquet'

# Optional (for SMT):
MNQ_5M = BASE / 'MNQ_continuous_5min.parquet'
```

### NQ Baseline Script
**Before**: `bear_nq_sweep_1h_baseline.py` loaded NQ data  
**Now**: `bear_nq_sweep_1h_baseline.py` loads **MNQ data**

```python
# Required:
MNQ_5M = BASE / 'MNQ_continuous_5min.parquet'
MNQ_1H = BASE / 'MNQ_continuous_1H.parquet'

# Optional (for SMT):
MES_5M = BASE / 'MES_continuous_5min.parquet'
```

---

## What You Can Run Now

If you have MES and MNQ data:

```zsh
# ES baseline (from MES data)
python strategies/bear_es_sweep_1h_baseline.py

# NQ baseline (from MNQ data)
python strategies/bear_nq_sweep_1h_baseline.py
```

Both scripts will work immediately. No need to obtain ES or NQ data separately.

---

## SMT Divergence (Optional Enhancement)

If you want to test SMT divergence (comparing MES vs MNQ breaks):
- ES baseline will use MNQ if available for SMT
- NQ baseline will use MES if available for SMT

If these files are missing, scripts gracefully fall back (no SMT testing, no error).

---

## Bottom Line

✅ **You can proceed with MES and MNQ data only.**  
❌ **You do not need to obtain ES and NQ separately.**

The sweep pattern is the same. The research will be identical. Run the baselines today.

