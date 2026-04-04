# Story — Strategy Family Definitions

## Status
draft

## Priority
P2 — Research Clarity. As the number of strategies grows, `logic_type + direction` becomes a
junk-drawer bucket. Noisy cross-artifact correlations reduce the value of
`get_cross_artifact_correlation_v1` and make alpha comparison unreliable. This story defines what
constitutes a "family" before that noise accumulates.

## Summary
Define a formal taxonomy for strategy families that makes cross-artifact correlation trustworthy
and lays the groundwork for a `family_id` property in V2. No schema changes in V1; the output
is a design specification and a mapping from current `logic_type + direction` groupings to the
proposed taxonomy.

## Problem
In V1, `get_cross_artifact_correlation_v1` groups strategies by `logic_type + direction`. As the
repo grows, this grouping becomes too broad:

- "Mean Reversion Long" may contain RSI-based dip buying, Bollinger Band reversion, and
  VWAP-reversion — three strategies with fundamentally different signal sources that should not
  be compared directly.
- "Trend Following Bear" may include EMA crossover, dual-timeframe, and momentum strategies
  that share direction but differ in entry/exit logic.

When these are treated as the same "family," the cross-artifact query returns correlated noise:
the ES and NQ variants look similar on the surface, but their edge cases diverge. An LLM or
researcher acting on this data will reach false conclusions.

## Goal
Produce a stable taxonomy specification that:
1. Defines the levels of a strategy family hierarchy (V1 current → V2 proposed).
2. Identifies candidate `family_id` values and how they would be derived.
3. Maps existing strategies in the repo to the proposed taxonomy.
4. Documents how `get_cross_artifact_correlation_v1` should evolve to filter by `family_id`.

This is a design document first. Implementation (schema changes) is a V2 story.

## Inputs
- `strategies/` — current strategy implementations (source of truth for logic families)
- `research/graph/query.py` — `GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER` (current correlation axis)
- `research/graph/query_models.py` — `CrossArtifactRowV1` (current output shape)
- `docs/graph_v1_contract.md` — canonical `Strategy` node properties
- `research/results/registry.json` — existing strategy names as a practical family inventory

## Taxonomy Specification

### Level 1 — Core Logic (Current V1, canonical)
Property: `logic_type` on the `Strategy` node.
Examples: `MeanReversion`, `TrendFollowing`, `Momentum`, `Sweep`.
Purpose: Broad category. Useful as a first-pass grouping but insufficient for alpha comparison.

**V1 status:** Implemented. Exposed in `CrossArtifactRowV1`.

### Level 2 — Signal Family (Proposed V2)
Property: `family_id` on the `Strategy` node (new field, not in V1 schema).
Definition: Shared mathematical source. Strategies within the same `family_id` use the same
base indicator logic and share meaningful alpha comparison semantics.

Candidate identifiers:
- **Source code hash:** SHA of the specific strategy class in `strategies/`. Immutable once
  the logic is frozen. Changes when the signal changes.
  Example: `sha256(strategies/rsi_reversion.py)[:12]` → `family_id = "rsi_rev_a1b2c3"`
- **Primary anchor indicator:** Human-readable label for the main entry signal.
  Example: `rsi`, `ema_crossover`, `vwap_reversion`, `dual_tf`
- **Composite key:** `{primary_anchor}_{logic_type}_{version}` for stable, human-readable IDs.
  Example: `rsi_mean_reversion_v1`

Recommendation: Use the composite key as the `family_id` value. It is human-readable, stable
across instrument variants, and does not require hashing infrastructure.

**V1 status:** Not implemented. Spec only. No schema changes until V2.

### Level 3 — Parameter Variant (Informational, no schema change)
Definition: Strategies within the same `family_id` that differ only by lookback periods,
thresholds, or timeframe granularity.
Utility: Identifying the "peak of a parameter mountain" across ES and NQ — i.e., which
parameter set generalises across instruments.

No new node property needed. Variants within a family are already differentiated by `Config`
node `params_json`. The family comparison query would aggregate over them.

### Level 4 — Timeframe Group (Proposed, informational)
Definition: Grouping `5m`, `15m`, and `30m` into an "Intraday" bucket; `1H`, `4H` into
"Swing". Useful for queries like "how does this family perform on intraday vs swing timeframes?"

Candidate property: `timeframe_group` on `Strategy`, derived at ingest from `timeframe`.
Mapping:
```
5m, 15m, 30m → intraday
1H, 4H       → swing
1D           → daily
```

**V1 status:** Not implemented. Informational only.

## Mapping: Current Repo Strategies → Proposed Taxonomy

| Strategy file | logic_type | direction | family_id (proposed) | timeframe_group |
|---|---|---|---|---|
| `rsi_reversion.py` | `MeanReversion` | `bear`/`bull` | `rsi_mean_reversion_v1` | swing / intraday |
| `ema_crossover.py` | `TrendFollowing` | `bear`/`bull` | `ema_crossover_v1` | swing |
| `mars.py` | `Momentum` | `bull` | `mars_momentum_v1` | swing |
| `dual_tf_trend.py` | `TrendFollowing` | `bear`/`bull` | `dual_tf_trend_v1` | swing |

Note: "sweep" strategies (grid-search variants) share the `family_id` of their base strategy.
The `logic_type = sweep` label denotes the run type, not the signal family.

## Impact on `get_cross_artifact_correlation_v1`

Current Cypher filters on `logic_type = anchor.logic_type AND direction = anchor.direction`.
With `family_id` in V2, this becomes:
```cypher
WHERE related.family_id = anchor.family_id
  AND related.strategy_id <> anchor.strategy_id
```

This produces meaningfully correlated results: RS Reversion on ES vs NQ, not
"all bear strategies" which may include EMA crossover and RSI reversion side by side.

The `CrossArtifactRowV1` DTO would gain a `family_id` field, and `logic_type` becomes
redundant as the primary filter axis (though retained for backward compatibility).

## V1 Behaviour (No Change)
The V1 query continues to use `logic_type + direction`. This document acknowledges the
limitation and defers schema changes to V2. The spec here prevents the V2 implementation
from being designed ad hoc.

## Deliverable
- This document, reviewed and approved.
- A populated taxonomy mapping table (above) extended to all strategies in the repo.
- A draft `family_id` naming convention ratified by the operator.
- A follow-on story: "Add `family_id` to `Strategy` node schema and migration path."

## In Scope
- Taxonomy levels 1–4 defined and documented.
- Candidate `family_id` identifiers evaluated with pros/cons.
- Existing strategies mapped to proposed taxonomy.
- Impact on `get_cross_artifact_correlation_v1` documented.
- V1 vs V2 migration path sketched.

## Out of Scope
- Schema changes to `Strategy` node in V1.
- Changes to ingestion parsers.
- Automated `family_id` derivation tooling.
- Benchmark basket composition (separate open question in `graph_v1_contract.md`).

## Acceptance Criteria
- [ ] Taxonomy levels 1–4 defined, each with candidate values and implementation status.
- [ ] At least one candidate `family_id` naming convention selected with rationale.
- [ ] All current strategies in `strategies/` mapped to `family_id` in the table.
- [ ] Impact on `get_cross_artifact_correlation_v1` Cypher documented.
- [ ] V1 limitation acknowledged; V2 migration path sketched (schema delta + migration query).
- [ ] Follow-on V2 story written and added to unsorted stories.

## Validation
- Operator review of taxonomy mapping table.
- Cross-check against `strategies/` directory — every `.py` file must appear in the table.
- Dry-run: apply proposed `family_id` filter to current seeded graph and verify correlation
  results narrow meaningfully vs the current `logic_type + direction` filter.

## Definition of Done
- [ ] Taxonomy document approved and committed.
- [ ] Mapping table complete and cross-checked.
- [ ] `family_id` convention ratified.
- [ ] Follow-on V2 implementation story created.
- [ ] Story marked CLOSED after operator sign-off.

## Dependencies
- Depends on: `spike_lean_neighborhood_optimization.md` — Option D (curated ingestion) is
  the long-term payoff of having stable family definitions.
- Enables: V2 `family_id` schema story.
- Enables: Trustworthy `get_cross_artifact_correlation_v1` at scale.

## Open Questions
- Should `family_id` be operator-assigned at ingest (`qw record --family-id rsi_mean_reversion_v1`)
  or derived automatically from a source code hash?
- Is `family_id` a `Strategy` property or a separate `Family` node with `BELONGS_TO` edges?
  (Node approach supports richer queries; property approach is simpler and V1-compatible.)
- How should parameter variants (Level 3) be surfaced in the cross-artifact query —
  as separate rows or aggregated?

## Notes
This story is prerequisite for trustworthy alpha comparison across instruments. The current
`logic_type + direction` grouping is adequate for a 4-strategy repo; it becomes misleading at
10+ strategies. Draft this before ingestion volume scales, not after.
