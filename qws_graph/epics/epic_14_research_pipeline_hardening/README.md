# Epic 14 — Research Pipeline Hardening

## Objective

Eliminate regime-concentration blind spot; add upstream quality gates; fix Cypher bug;
seed literature library. All work is additive — no breaking changes to existing output,
no graph schema changes.

## Entry Criteria

- Epic 13 QWS-1303 CLOSED (trial pipeline stable)
- ArcticDB store.write_signals() available (QWS-1000 CLOSED)
- qw monitor + qw degrade exist (QWS-1405 prerequisite satisfied)
- Literature pipeline built (Epic 26.4, commit 37daf27)

## Exit Criteria

- Annual P&L breakdown in every trial report
- Regime diversity gate wired into `qw record --bundle`
- ATR regime labels seeded for CL_1H, MES_1H, BTC/USD_1H
- Redundancy gate Cypher bug fixed with regression test
- Champion degradation advisory operational
- ≥5 papers ingested; search_library returns ≥2 hits for "mean reversion futures" and "regime switching"

## Schema Changes

One new optional property: `degrade_reason` (str, nullable) on FormerChampion node.
Written by `qw degrade --reason`; not auto-populated. Declared in `data_dictionary.yaml` and `PROVENANCE_ENGINE.md`.
Diversity score written to existing `trial_metadata` map on Run node (no new property).

## Implementation Phases

| Phase | Stories | Theme |
|---|---|---|
| 1 — Bugfix | QWS-1404 | Fix redundancy gate Cypher |
| 2 — Diagnostics | QWS-1401 | Year-by-year P&L |
| 3 — Content | QWS-1406 | Seed literature library |
| 4 — Gate | QWS-1402 | Regime diversity gate (after 1401) |
| 5 — Labels | QWS-1403 | ATR regime pre-labels |
| 6 — Advisory | QWS-1405 | Champion degradation advisory |

## Story Execution Order

```
QWS-1404 (bugfix — fast, unblocks research queries)
QWS-1401 (year-by-year P&L — unblocks 1402)
QWS-1406 (literature seed — no code, parallel with 1401)
    └── QWS-1402 (diversity gate — after 1401)
QWS-1403 (ATR regime labels — independent)
QWS-1405 (champion advisory — independent, lowest urgency)
```

## Stories

| Story | ID | Status | Effort | Blocked On |
|---|---|---|---|---|
| Year-by-Year P&L in Trial Output | QWS-1401 | READY | S | — |
| Regime Diversity Gate | QWS-1402 | READY | S | QWS-1401 |
| Rule-Based Regime Pre-Labels | QWS-1403 | READY | M | — |
| Fix Redundancy Gate Cypher Bug | QWS-1404 | READY | S | — |
| Champion Degradation Advisory Rule | QWS-1405 | READY | S | — |
| Seed Literature Pipeline | QWS-1406 | READY | S | — |

## Approach Constraints

- All changes additive — no breaking changes to existing evaluator output
- No auto-rejection anywhere — all gates are warnings only
- ATR labels use prefix `regime_atr_` to avoid collision with Epic 12 HMM (`regime_hmm_`)
- No graph schema changes — diversity score goes into existing `trial_metadata` map
- Epic 14 completes before Epic 12 (ML Research) begins
