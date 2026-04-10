# NQ Bull Sweep 4H v1

**Status**: Frozen (Phase 4 complete)
**Freeze Date**: 2026-04-03

---

## Config (Champion)

- Instrument: NQ
- Direction: BULL
- Sessions: LONDON, NY
- Sweep timeframe: 4H
- target_r: 1.25
- atr_mult_stop: 0.7
- wick_mode: q1_only
- chain_mode: confirm_breakout
- stop_mode: 5m_lower_high
- max_hold_bars: 48

---

## IS Metrics (Champion)

- Sample size: 52
- Win rate: 0.4808
- Breakeven win rate: 0.4444
- Avg R/trade: 0.0710
- Total R: 3.69
- Profit factor: 1.19
- Sharpe: 1.11
- Max drawdown (R): -5.80

---

## Why This Works

The 4H bull sweep setup keeps the sample small but cleaner, and the Q1 wick filter preserves the highest-quality continuation attempts in trend-friendly conditions.

---

## Known Fragilities

1. Performance is concentrated in a narrow session mix and could degrade if LONDON momentum weakens.
2. The setup depends on orderly continuation after the sweep; choppy consolidation can erase the edge quickly.
3. The 4H sample is still relatively thin, so a modest streak of losers can distort observed Sharpe.

---

## OOS Command (Champion)

```zsh
python strategies/nq_bull_sweep_4h_q1_only_v1.py --live --pivot-from c3d4e5f6a1b2

# Record OOS result:
qw record --oos oos_pass \
  --champion <champion_id> \
  --sharpe 1.85          # optional — records OOS Sharpe for drift analysis
```

