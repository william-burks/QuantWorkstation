# Story 2 — Promotion Alerts

## ID
QWS-0405

## Status
READY

## Blocked On
QWS-0407 — requires `active_window_frequency` property on Run nodes (populated at ingest time)
and `MIN_ACTIVE_WINDOW_FREQUENCY` constant added to `research/experiments/standards.py`

## Summary
After a successful `baseline_csv` ingest, check each persisted Run against the existing
`standards.py` thresholds and print a promotion candidate notice if any qualify. No new
config file. No auto-ingest. Human stays in the loop.

## Problem
A run that clears the `professional` or `institutional` tier threshold produces no signal
at ingest time. The operator must separately open `index.html`, read the results, remember
the threshold numbers, and decide whether to run the golden script. This is:
- Inconsistent (the bar shifts depending on who is looking)
- Silent (passing runs are indistinguishable from marginal ones in terminal output)

The thresholds already exist in `research/experiments/standards.py`. They are not being
used post-ingest.

## Goal
After `qw record --kind baseline_csv` completes, emit a notice for any run that clears
the `professional` tier:

```
[PROMOTION CANDIDATE] run_id=a1b2c3d4e5f6
  sharpe=2.31  profit_factor=2.1  win_rate=0.66  trades=45  tier=professional
  → Run golden: ./research/bin/run_liquidity_sweep_golden.sh
```

No file written. No graph change. Just stdout.

## Design

### Where the check runs
In `cli.py`, after `store.persist()` returns successfully for a `baseline_csv` ingest.
Evaluate only `Run` objects whose ingest status is `persisted` (not `skipped`).

### Threshold source
Import directly from `research/experiments/standards.py`:
```python
from research.experiments.standards import (
    SHARPE, PROFIT_FACTOR, MAX_DRAWDOWN_LIMIT, MIN_TRADES_PER_YEAR,
    MIN_ACTIVE_WINDOW_FREQUENCY,  # added by QWS-0407
)
```
The `professional` tier keys define the floor. No `promotion_rules.yaml` needed.

Promotion alert fires only when ALL of the following are met:
- `sharpe >= SHARPE["professional"]`
- `profit_factor >= PROFIT_FACTOR["professional"]`
- `total_trades >= 30`
- `active_window_frequency >= MIN_ACTIVE_WINDOW_FREQUENCY` (0.06 trades/day)

Runs where `active_window_frequency` is null (ingested before QWS-0407) are silently
excluded — null-safe guard required.

### Output format
One block per qualifying run, printed after the normal ingest summary. Silent if no runs
qualify. Never blocks the ingest (exceptions in the check are caught and suppressed).

## In Scope
- `qws_graph/research/graph/cli.py` — post-ingest evaluation block in `_cmd_record`
- Read-only use of `research/experiments/standards.py` thresholds
- Unit tests for the evaluation logic (isolated from CLI)

## Out of Scope
- `promotion_rules.yaml` config file (thresholds come from `standards.py` directly)
- `--auto-promote` flag (human runs golden script manually)
- Writing draft `champion_md` files
- Grid CSV evaluation (too many runs; promotion logic for grids is a separate problem)
- Any graph writes

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — post-ingest hook
- `research/experiments/standards.py` — read-only threshold import
- `qws_graph/tests/unit/test_promotion_alerts.py` — new

## Acceptance Criteria
- [ ] After ingesting a Run with sharpe = 2.3, profit_factor = 2.1, max_drawdown = -0.08,
  total_trades = 45, active_window_frequency = 0.10: promotion candidate block is printed to stdout.
- [ ] After ingesting a Run with sharpe = 0.9 (below professional threshold): no block printed.
- [ ] A run with active_window_frequency = 0.03 (below 0.06 floor) and otherwise-passing
  sharpe/profit_factor/trades produces no alert.
- [ ] A run where active_window_frequency is null (pre-QWS-0407 legacy run) produces no alert.
- [ ] Skipped runs (significance gate) produce no alert.
- [ ] Grid CSV ingests produce no alert.
- [ ] An exception in the evaluation block does not prevent the receipt from being written.
- [ ] Output is silent when no run qualifies (no "no candidates" message).

## Definition of Done
- [ ] Evaluation logic implemented and unit tested.
- [ ] Post-ingest hook live in `cli.py`.
- [ ] Story marked CLOSED.
