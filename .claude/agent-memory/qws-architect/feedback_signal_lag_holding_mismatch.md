---
name: Signal lag vs holding period evaluation pattern
description: Evaluation rule — regime signals with lag >> holding period need evidence that cheaper same-domain signals are insufficient before approval
type: feedback
---

When evaluating candidate signals where signal lag significantly exceeds system holding period (e.g., weeks vs hours):

1. Regime conditioning is the ONLY viable use path — direct entry/exit timing is architecturally impossible
2. Check if cheaper/simpler signals already serve the same regime domain (e.g., BDTI covers tanker rates cheaper than AIS vessel tracking)
3. Marginal information over existing signals must be quantified or at least hypothesized with a testable claim — "more granular data" alone is not justification
4. Cost must be proportional to personal-tool scale — $200/mo recurring for speculative regime feature fails cost test
5. Implementation complexity matters — geofencing/dedup/mapping vs single REST endpoint is a 10x complexity delta for unproven marginal value

**Why:** AIS Tanker Flow Tracker evaluation (2026-04-12) revealed pattern: speculative alternative data sources that overlap existing planned signals (BDTI, EIA) at higher cost/complexity should be rejected until cheaper signals prove insufficient.

**How to apply:** Any candidate with signal_lag > 10x holding_period gets automatic MISALIGNED unless: (a) no cheaper signal covers same domain, (b) evidence exists that domain regime context improves alpha for target holding period, (c) cost is free or trivial.
