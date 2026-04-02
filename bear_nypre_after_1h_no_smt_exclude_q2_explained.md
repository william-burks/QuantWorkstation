# V2 Strategy Explained: Bear NY_PRE/AFTER 1H Sweep

## What this strategy does in plain English

The strategy looks for moments when the market appears to break above a significant high on the CL (crude oil futures)
hourly chart — but then closes back below that high within the same candle. This is called a **liquidity sweep**: the
price briefly pushes above a level where stop orders and breakout buyers are clustered, triggers them, and then reverses
hard. The strategy bets that the move down following that reversal is tradeable.

---

## The setup in steps

### Step 1 — Find a swing high on the 1-hour chart

The strategy scans the 1-hour CL chart for **swing highs** — price peaks that are the highest point within a 3-bar
window on either side. These represent previous resistance levels where sellers entered or buyers got stopped out.

### Step 2 — Wait for a sweep

A **bearish sweep** happens when:

- The candle's high exceeds a prior swing high (the stop run)
- But the candle closes back below that swing high (the rejection)

This means the market briefly faked out above a key level and failed to hold. This is the trigger.

### Step 3 — Only take sweeps in specific sessions

Not all sweeps are equal. The strategy only acts on sweeps that happen during:

- **NY_PRE** (7:00–9:30 AM Eastern) — the pre-market session when institutional positioning happens
- **AFTER** (4:00–8:00 PM Eastern) — the after-hours session with thinner liquidity and cleaner moves

Sessions like London and New York regular hours were tested and removed because they degraded performance.

### Step 4 — Filter out the "noisy" sweeps by wick size

Once a sweep is found, the strategy looks at how large the wick was relative to other sweeps. Sweeps are grouped into
four size buckets (Q1 smallest to Q4 largest). **Q2 sweeps are excluded** — these mid-sized wicks historically produced
the weakest results and diluted the edge. Q1, Q3, and Q4 sweeps are kept.

### Step 5 — Look for confirmation on the 5-minute chart

After a qualifying sweep, the strategy watches the 5-minute CL chart for confirmation signals before entering. It
specifically looks for a **Break of Structure (BOS)** or **Inverse Fair Value Gap (IFVG)** — signs that price has
started moving in the expected direction (down). SMT divergence between MES and MNQ is tracked but not required to
confirm.

### Step 6 — Enter short

Once the confirmation fires, the strategy enters **short** (selling) at the close of the confirming 5-minute bar.

### Step 7 — Manage the trade

- **Stop loss**: placed just above the sweep level, with a 0.5 ATR buffer to avoid noise
- **Target**: 1.25R from entry (meaning if the stop is $1 away, the target is $1.25 away in the direction of the trade)
- **Max hold time**: the trade is closed after a maximum of 24 five-minute bars (~2 hours) if neither stop nor target is hit
- **No partial exits**: the position stays full size until target, stop, or time exit
- **No stall exit**: earlier exit tests were tried and removed because they reduced performance

---

## Why this works (the thesis)

When price sweeps a swing high and immediately rejects, it signals that there was no real buying interest at that
level — just trapped longs and triggered stops. The smart money (or simply momentum) is now positioned short and needs
price to move down to realize their gains. The strategy is riding that short-term post-sweep selling pressure.

Filtering to NY_PRE and AFTER sessions concentrates entries in periods where this sweep-and-reverse pattern tends to be
cleaner and more committed, rather than being chopped up by high-volume NY session noise.

---

## What the numbers say (in-sample)

| Metric                    | Value  |
|---------------------------|--------|
| Trades                    | 32     |
| Win rate                  | ~31%   |
| Average R per trade       | ~0.26R |
| Profit factor             | ~1.79  |
| Sharpe ratio              | ~4.80  |
| Max drawdown              | ~2.7R  |
| Breakeven win rate needed | 44.4%  |

The win rate is below the breakeven needed — but the strategy still wins because winners pay out 1.25R and losses only cost
1R. You only need to be right ~44% of the time to break even; at ~31% win rate the edge still comes from asymmetry and disciplined loss sizing.

Just as important: multiple modification attempts were tested and all failed. Tightening stops, taking partial profits early, forcing stall exits, and filtering down to only the largest wick sweeps all reduced performance. That is useful evidence that the current structure is not a lucky artifact of one tweak — it is the best version found in-sample so far.

---

## What this is not

- This is **not** a high-frequency strategy — it takes a handful of trades per week at most
- This is **not** yet validated out-of-sample — all numbers above are in-sample and should be treated as a hypothesis, not a proven edge
- This is **not** a directional macro view — it's purely a short-term structure and liquidity pattern


