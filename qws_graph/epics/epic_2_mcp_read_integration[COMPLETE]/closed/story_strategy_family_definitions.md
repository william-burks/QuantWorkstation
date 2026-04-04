# Story — Strategy Family Definitions

## Status
CLOSED

## Priority
P2 — Research Clarity. As the number of strategies grows, `logic_type + direction` becomes a
junk-drawer bucket. Noisy cross-artifact correlations reduce the value of
`get_cross_artifact_correlation_v1` and make alpha comparison unreliable. This story defines what
constitutes a "family" before that noise accumulates.

## Summary
Define a formal taxonomy for strategy families that makes cross-artifact correlation trustworthy
and documents the `family_id` property added to `Strategy` nodes in Churn Story 1. This story
was originally scoped as "spec only, no schema changes in V1." During implementation of Churn
Story 1, `family_id` was added to V1 ahead of schedule. This document is updated to reflect the
actual implementation.

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
2. Documents the chosen `family_id` derivation and how it is set at ingest.
3. Maps existing strategies in the repo to the implemented taxonomy.
4. Documents how `get_cross_artifact_correlation_v1` uses `family_id` in V1.

## Inputs
- `strategies/` — current strategy implementations (source of truth for logic families)
- `research/graph/query.py` — `GET_CROSS_ARTIFACT_CORRELATION_V1_CYPHER` (current correlation axis)
- `research/graph/query_models.py` — `CrossArtifactRowV1` (current output shape)
- `docs/graph_v1_contract.md` — canonical `Strategy` node properties
- `research/results/registry.json` — existing strategy names as a practical family inventory

## Taxonomy Specification

### Level 1 — Core Logic (V1, canonical)
Property: `logic_type` on the `Strategy` node.
Examples: `MeanReversion`, `TrendFollowing`, `Momentum`, `Sweep`.
Purpose: Broad category. Useful as a first-pass grouping but insufficient for alpha comparison.

**V1 status:** Implemented. Exposed in `CrossArtifactRowV1`.

### Level 2 — Signal Family (V1, implemented in Churn Story 1)
Property: `family_id` on the `Strategy` node.

**Derivation (implemented):** `hash12(normalize_text(logic_type), normalize_text(direction), source_hash)`
where `source_hash = SHA256(strategy_source_bytes)[:12]`.

Set at ingest via `qw record --source-file <path/to/strategy.py>`. When `--source-file` is
omitted, `family_id` is `None` and the Strategy node falls back to the `logic_type + direction`
correlation axis in `get_cross_artifact_correlation_v1`.

**Why hash-based derivation over composite keys:**
The original spec proposed a human-readable composite key (`rsi_mean_reversion_v1`). The
implemented approach uses a hash because:
- No operator naming burden — derivation is automatic from the source file.
- Immutable once logic is frozen — changing signal code produces a new hash.
- Instrument-independent by construction — ES and NQ variants of the same strategy will share
  a `family_id` when ingested with the same `--source-file`.
- Version-safe — a rewrite of `rsi_reversion.py` gets a new `family_id` without renaming.

The tradeoff is that `family_id` values are not human-readable (12-char hex). The correlation
query output should be interpreted via `logic_type + direction` labels for human display.

**V1 status:** Implemented. Exposed in `CrossArtifactRowV1` as optional `family_id` field.

### Level 3 — Parameter Variant (Informational, no schema change)
Definition: Strategies within the same `family_id` that differ only by lookback periods,
thresholds, or timeframe granularity.
Utility: Identifying the "peak of a parameter mountain" across ES and NQ — i.e., which
parameter set generalises across instruments.

No new node property needed. Variants within a family are already differentiated by `Config`
node `params_json`. The family comparison query aggregates over them.

### Level 4 — Timeframe Group (Informational, no schema change)
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

## Mapping: Current Repo Strategies → Implemented Taxonomy

| Strategy file | logic_type | direction | family_id derivation | timeframe_group |
|---|---|---|---|---|
| `rsi_reversion.py` | `MeanReversion` | `bear`/`bull` | `hash12("meanreversion", "bear"/"bull", src_hash)` | swing / intraday |
| `ema_crossover.py` | `TrendFollowing` | `bear`/`bull` | `hash12("trendfollowing", "bear"/"bull", src_hash)` | swing |
| `mars.py` | `Momentum` | `bull`/`bear` | `hash12("momentum", "bull"/"bear", src_hash)` | swing |
| `dual_tf_trend.py` | `TrendFollowing` | `bear`/`bull` | `hash12("trendfollowing", "bear"/"bull", src_hash)` | swing |
| `bear_es_sweep_1h_baseline.py` | `Sweep` | `bear` | Not applicable — standalone simulation script | swing |
| `bear_nq_sweep_1h_baseline.py` | `Sweep` | `bear` | Not applicable — standalone simulation script | swing |

Notes:
- `bear_es_sweep_1h_baseline.py` and `bear_nq_sweep_1h_baseline.py` are standalone liquidity
  sweep simulation scripts, not `BaseStrategy` subclasses. They are not ingested via
  `qw record --source-file`. Their registry entries (`es_bear_sweep_1h_v1`,
  `liquidity_sweep`, `liquidity_sweep_golden`) use `logic_type = Sweep` with `family_id = None`.
- `dual_tf_trend.py` and `ema_crossover.py` both have `logic_type = TrendFollowing`. They will
  receive different `family_id` values because their `source_hash` inputs differ.
- `mars.py` supports both `bull` and `bear` direction variants via parameterisation. Each
  direction produces a distinct `family_id`.

## Impact on `get_cross_artifact_correlation_v1`

Implemented in Churn Story 1. The Cypher uses a conditional OR branch:

```cypher
WHERE (anchor.family_id IS NOT NULL AND related.family_id = anchor.family_id
       AND related.strategy_id <> anchor.strategy_id)
   OR (anchor.family_id IS NULL
       AND related.logic_type = anchor.logic_type
       AND related.direction = anchor.direction
       AND related.strategy_id <> anchor.strategy_id)
```

- When `family_id` is populated: correlation is scoped to strategies sharing the same source
  logic, instrument-independent. This is the intended V2 behaviour.
- When `family_id` is `None`: falls back to `logic_type + direction`. Pre-family Strategy nodes
  retain meaningful correlation without migration.

`CrossArtifactRowV1` gained `family_id: str | None = None` to surface the grouping axis to
callers.

## V1 Behaviour (Implemented)
`family_id` is in V1 schema. It is optional (`null` for nodes ingested without `--source-file`).
The fallback branch in the correlation Cypher preserves backward compatibility. No migration
needed for existing nodes unless cross-artifact correlation on family-scoped axis is required for
pre-existing strategies.

## Deliverable
- This document, reviewed and updated to reflect Churn Story 1 implementation.
- Taxonomy mapping table complete for all 6 strategy files.
- `family_id` naming convention ratified: **hash-based auto-derivation** via `--source-file`.
- Follow-on V2 story: `story_family_id_backfill_migration.md` — backfill `family_id` on
  pre-existing Strategy nodes by re-ingesting with `--source-file`.

## In Scope
- Taxonomy levels 1–4 defined and documented.
- `family_id` derivation documented with rationale.
- All current strategy files mapped to proposed taxonomy, including sweep scripts.
- V1 correlation Cypher documented (OR-branch fallback).
- V1 vs V2 migration path: backfill story written.

## Out of Scope
- Changes to ingestion parsers beyond `--source-file` flag (already done in Churn Story 1).
- `timeframe_group` property (informational only, deferred).
- Automated `family_id` derivation without `--source-file` (considered; rejected in favour of
  explicit operator control).

## Acceptance Criteria
- [x] Taxonomy levels 1–4 defined, each with candidate values and implementation status.
- [x] At least one candidate `family_id` naming convention selected with rationale.
  **Selected:** hash-based auto-derivation. Rationale documented above.
- [x] All current strategies in `strategies/` mapped to `family_id` in the table.
  Includes all 6 files: `rsi_reversion.py`, `ema_crossover.py`, `mars.py`, `dual_tf_trend.py`,
  `bear_es_sweep_1h_baseline.py`, `bear_nq_sweep_1h_baseline.py`.
- [x] Impact on `get_cross_artifact_correlation_v1` Cypher documented.
  OR-branch implementation documented above.
- [x] V1 limitation acknowledged; V2 migration path sketched.
  `family_id` is in V1. Backfill path documented in follow-on story.
- [x] Follow-on V2 story written and added to unsorted stories.
  See `story_family_id_backfill_migration.md`.

## Definition of Done
- [x] Taxonomy document approved and committed.
- [x] Mapping table complete and cross-checked.
- [x] `family_id` convention ratified.
- [x] Follow-on V2 implementation story created.
- [x] Story marked CLOSED after operator sign-off.

## Dependencies
- Depends on: `spike_lean_neighborhood_optimization.md` — CLOSED.
- Depends on: Churn Story 1 (`story_family_definitions_significance_filtering.md`) — CLOSED.
  Schema changes (`family_id`, `source_hash` tooling, `--source-file` CLI flag) were implemented
  there ahead of this story's original spec.
- Enables: `story_family_id_backfill_migration.md` — pre-existing node backfill.
- Enables: Trustworthy `get_cross_artifact_correlation_v1` at scale (implemented).

## Open Questions (resolved)
- **Should `family_id` be operator-assigned or auto-derived?**
  Resolved: auto-derived from `--source-file` hash. Operator provides the source file; the
  system derives the ID.
- **Is `family_id` a `Strategy` property or a separate `Family` node?**
  Resolved: property on `Strategy`. Simpler, V1-compatible, sufficient for current query needs.
- **How should parameter variants be surfaced?**
  Deferred to Level 3 (informational). The correlation query aggregates over Config variants
  within the same family. No separate surface needed in V1.

## Notes
This story is prerequisite for trustworthy alpha comparison across instruments. The current
`logic_type + direction` grouping is adequate for a 4-strategy repo; it becomes misleading at
10+ strategies. Churn Story 1 resolved the critical schema gap ahead of schedule.
