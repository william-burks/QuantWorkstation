# Epic 15 — Data Infrastructure Quality & Provenance

> **Status:** PLANNED — insert before Epic 12 ML Research
> **Inspiration:** Two Sigma "Treating Data as Code" (Effie Baram, Head of Foundational Data Engineering)
> **Split:** Phase A (Data Health, 6 stories) → Phase B (Provenance Layer, 5 stories)
> **Sequence:** Epic 13 QWS-1304 → Epic 14 QWS-1406 → **Epic 15a → Epic 15b** → Epic 12

---

## Epic-Level Definition of Done

All stories in this epic must satisfy the following before closing:

- `make verify` passes (ruff, mypy, pytest) — no new warnings or failures
- New env vars added to `data/config.py` `Settings` class with typed defaults
- New exception classes (`SchemaError`, `RollAnomalyError`) defined in `data/validation.py` — importable from that module
- Files touched match each story's Repo Touchpoints list exactly
- `BACKLOG_ALIGNMENT.md` "Not Yet Implemented" table updated for any new graph nodes/edges prior to Phase B implementation beginning
- Story-specific RESEARCH_WORKFLOW.md or PROVENANCE_ENGINE.md doc updates are explicit ACs, not narrative mentions

---

## Why This Epic Exists

The Two Sigma article articulates a principle that directly applies to QWS:

> "Companies depending on external data sources frequently encounter unpredictable schema changes, delivery delays, and quality issues that can cascade through their systems. Without proper data platform capabilities — including automated quality checks, data lineage tracking, and proactive alerting — these issues can result in silent failures."

QWS already has strong research lineage (provenance graph, BRANCHED_FROM, SUPERSEDED_BY, decay monitoring, dual-hurdle gates). The gap is in the **data layer below the research loop** — the bars and series that strategies consume. That layer has no observability, no quality telemetry, no reproducibility across reseeds, and no contracts.

### The Critical Reframe: Trading Research ≠ Enterprise Data Warehouse

| Enterprise goal | Trading research goal |
|---|---|
| Data is mostly right, freshness within SLA | Every bar is either trusted, versioned, reproducible — or it doesn't exist |
| Fix bad row → update record | Fix bad row → you rewrote history → every prior backtest is now a lie |
| Distribution shift = data quality issue | Distribution shift = silent alpha contamination |
| "Did the data arrive?" | "Will a backtest run today produce the same result as last month?" |
| Vendor revision = noise to fix | Vendor revision = signal; must be detected and versioned |
| Gap in delivery = dashboard staleness | Gap in delivery = corrupted signal, potentially a bad trade |
| Look-ahead in pipeline = bug | Look-ahead **in the adjustment chain itself** (CONTFUT ratio) = structural research validity problem |
| SLA breach = operational incident | Bad bar in RTH for ≤4H strategy = direct P&L impact |

QWS's Manifesto constraint (holding ≤ 4H) makes every bar failure a first-class research validity event, not a monitoring footnote.

### Why Before Epic 12 ML Research

Epic 12 introduces feature engineering (QWS-1203) and ML walk-forward harness (QWS-1204). Both consume ArcticDB bars and computed features in ways that compound data quality failures:

- ML models trained on silently-revised CONTFUT data produce artifacts that cannot be detected post-hoc
- Feature pipelines built before input contracts exist have no declared dependency surface — silent reads of stale/wrong data
- 50+ ML Runs generated without snapshot infrastructure cannot be reproduced after a reseed
- Retrofitting provenance infrastructure after ML produces volume is expensive

**The seams not built before ML starts will stay absent.**

---

## Current State Assessment

### What QWS-1010 Delivered (the only data quality story closed)

`validate_bars()` in `data/validation.py` — a pre-write check only:
- Schema drift (missing OHLCV columns) — P2 warn
- UTC tz enforcement — P1 raise
- Duplicate timestamps — P1 raise
- NaN/zero/negative prices — P1 raise
- high < low / close-out-of-range — P1 raise
- Gap detection (>2× expected spacing) — P2 warn
- Stale feed (last bar > 3× spacing from now) — P2 warn
- Row count vs expected (95% threshold) — P3 warn

Note: `volume` is NOT in `_REQUIRED_COLS`. Stories that add volume validation must extend `_REQUIRED_COLS` or add it to the new `audit_symbol()` function.

**What QWS-1010 does NOT cover:**
- Post-write health of stored data (no way to audit what's already in ArcticDB)
- Anomaly detection on incoming data (statistical baseline, z-score alerts)
- Delivery monitoring for scheduled collectors (did last night's run succeed?)
- Vendor schema contract enforcement (Alpaca field changes, IBKR bar shape)
- Collection run persistence (no ledger of what ran, when, what changed)
- Any of the provenance gaps below

### The Full Gap Map

**Historical data:**

| Gap | Detail |
|---|---|
| No vintage / as-of | ArcticDB append overwrites on reseed. Zero record of what data looked like yesterday. Cannot reproduce a backtest from 30 days ago. |
| No data contract on stored symbols | `_FUTURES_KEY_RE` enforces key shape only. Zero enforcement on column set, dtypes, bar-freq grid, tz, null policy, volume semantics. |
| No quality telemetry | No row count history, no bar-gap log, no OHLC sanity stats persisted. Anomalies can only be discovered by human inspection. |
| No statistical baseline | No rolling distribution of returns/volume per symbol × tf. Distribution shift from vendor goes silent. |
| Reseed non-reproducibility | `reseed_*.py` is destructive. No snapshot of pre-reseed state. Two reseeds 1 week apart yield different ratio-adjusted series (new roll event), and old series is unrecoverable. |
| Ratio-adjust drift | `_ratio_stitch` recomputes cumulative ratio every seed. Every new roll rewrites entire history. Backtest run last month cannot be reproduced — absolute prices silently differ. |
| No point-in-time | CONTFUT is as-of today. Re-backtest in 2026 uses a 2026 ratio chain — look-ahead is embedded in the adjustment itself. |
| No source split | Alpaca 2yr + Databento 5yr overlap unmanaged. No provenance per bar. Which source wins on conflict? Undefined. |
| Libraries opaque | `list_symbols` gives names only. `symbol_meta()` does a full bar read just to return `rows` and `last_ts`. No cheap path for per-symbol manifest. |

**Live collection harness:**

| Failure mode | Current behavior | Impact |
|---|---|---|
| Malformed Alpaca bar (high<low, null close) | Stored, or whole batch rejected — no quarantine, no alert | Bad bar enters research loop silently |
| IBKR zero-open bar | Silently dropped. No count logged per batch. | Unknown data loss per collection run |
| Gap in delivery (Alpaca skips 3 hours) | Unnoticed if vendor never backfills | Strategy runs on gaps as if they're real |
| Delayed delivery | Next collect() picks it up. No SLO tracking. | No signal that yesterday's run missed a window |
| Vendor schema change (Alpaca adds/renames field) | AttributeError mid-loop or silent field drop | Intermittent failures, no root cause |
| Silent IBKR disconnect | `log.warning("No bars")`, continues to next symbol | Empty data written; no alarm |
| Roll ratio >20% (bad contract fetch) | Silently applied — corrupts entire stitched series | Garbage ratio-adjusted history |
| Re-run same window (crypto) | May re-append identical bars — no index dedupe | Duplicate timestamps in ArcticDB |
| No collection run record | Nothing persisted — can't verify "did last night's run succeed?" | Researcher running trials on stale data with no signal |

---

## Infrastructure Note: Store.get_symbol_info()

`symbol_meta()` in `data/store.py` performs a full `read_bars()` call — it reads the entire DataFrame to return `rows` and `last_ts`. Running it across 216+ symbol/TF combinations (24 futures roots × 9 timeframes + crypto) is too slow for a pre-session health check.

Before QWS-1501 or QWS-1504 can be implemented, add `Store.get_symbol_info(library, symbol)` to `data/store.py`. This wraps ArcticDB's native `lib.get_description(symbol)` which returns a `SymbolDescription` named tuple with `row_count`, `last_update_time`, and `date_range` without reading bar data. This is the correct cheap-metadata path for health scripts.

**This is a prerequisite for both QWS-1501 and QWS-1504. Implement it as the first step of whichever story ships first.**

---

## Phase A: Data Health (Epic 15a)

*Pre-condition for Phase B: provenance tooling is only meaningful over clean, verified data.*

### Phase A Sprint Ordering

Phase A stories are NOT all parallel-safe:

```
QWS-1501 ∥ QWS-1504               — no shared files; parallel-safe
QWS-1503 → QWS-1505               — both modify ibkr_futures.py; must be sequential
QWS-1510                           — blocked on QWS-1501 + QWS-1504
QWS-1502 (Alpaca schema)           — DEFERRED (post-MVP); crypto is not the MVP market
```

---

### QWS-1501 — ArcticDB Bar Health Report

**Goal:** Give the researcher a fast, authoritative audit of stored bar data before running a trial.

**Problem:** No current way to answer "are the bars in ArcticDB right now clean?" without writing a one-off script. Pre-session bar auditing is impossible. Trials run on data assumed clean.

**Implementation notes:**
- Use `Store.get_symbol_info()` (see Infrastructure Note above) for cheap per-symbol metadata; only fall back to `read_bars()` for gap detection which requires the full index
- Add `audit_symbol(library, symbol) -> dict` to `data/validation.py` — different signature from `validate_bars(df, freq)` (which takes a DataFrame); `audit_symbol` takes (lib, symbol) and calls store internally
- Script must enumerate `store.list_symbols('crypto')` and `store.list_symbols('futures')` — do NOT enumerate `futures_meta` lib (contract metadata, not OHLCV bars)
- Symbol key suffix parsing needed to infer timeframe for gap checks — reuse `_FUTURES_KEY_RE` pattern from `store.py`; all suffixes (`1H`, `4H`, `1D`, `1W`, etc.) must be verified to parse correctly with `pd.tseries.frequencies.to_offset()`

**Deliverable:** `scripts/bar_health.py`
- Uses `Store.get_symbol_info()` for row_count and date_range (fast path)
- Calls `audit_symbol()` for gap/stale/OHLC sanity checks on full bar data (slower path, skippable)
- Outputs per-symbol summary table: `symbol | rows | date_range | gap_count | stale | violations | status`
- Non-zero exit if any P1 violation found

**Files touched:** `scripts/bar_health.py` (new), `data/validation.py` (new `audit_symbol()`), `data/store.py` (new `get_symbol_info()`)

**Acceptance criteria:**
- [ ] Runs against live ArcticDB; covers `crypto` + `futures` libs; skips `futures_meta`
- [ ] Output table matches specified columns
- [ ] Non-zero exit on any P1 violation
- [ ] Performance: `time python scripts/bar_health.py` completes in <30s using `get_symbol_info()` fast path
- [ ] `RESEARCH_WORKFLOW.md` gains a `## Session Startup` section with the exact command `python scripts/bar_health.py` and a decision gate: "P1 violation = halt session, investigate before running trials"

---

### QWS-1502 — Vendor Schema Contract: Alpaca *(DEFERRED — post-MVP)*

> **Deferred 2026-04-25.** Crypto is the post-MVP market. Futures-first strategy means Alpaca schema validation is not on the critical path. Fully spec'd below for when crypto re-enters scope.

**Goal:** Catch Alpaca API schema changes before they enter ArcticDB.

**Problem:** Alpaca has changed the Bar object between API versions. Alpaca Bar objects are Pydantic models — missing fields won't raise `AttributeError`, they'll silently be `None`. Currently schema drift silently writes bad data or fails mid-collection with a cryptic error.

**Implementation notes:**
- Validator checks required fields via `getattr(bar, field, None) is None` — not `hasattr()` alone, because Pydantic always has the attribute
- `volume` is not in `validate_bars()` `_REQUIRED_COLS` — the vendor schema contract is the right place to enforce its presence from Alpaca
- `SchemaError(ValueError)` defined in `data/validation.py` — definitive choice; do not reuse bare `ValueError`
- Validator fires only on non-empty bar lists (`if not raw_bars: return`)
- `collect_all()` already catches `Exception` broadly — `SchemaError` propagates up from `collect()`, caught by `collect_all()`, logs and continues to next symbol (correct behavior; make it explicit)

**Deliverable:**
- `class SchemaError(ValueError): pass` in `data/validation.py`
- `_validate_vendor_schema(raw_bars: list) -> None` in `alpaca_crypto.py` before `_bars_to_df()`
- Pinned Alpaca Bar required fields: `open`, `high`, `low`, `close`, `volume`, `timestamp`
- On missing/None required field: raise `SchemaError` with field diff string (expected fields, missing fields)
- Unknown extra fields: log warning, do not block

**Files touched:** `data/collectors/alpaca_crypto.py`, `data/validation.py` (add `SchemaError`)

**Acceptance criteria:**
- [ ] `SchemaError` importable from `data/validation.py`
- [ ] Any Alpaca Bar with a None or missing required field raises `SchemaError` with diff before ArcticDB write
- [ ] Unknown extra fields log `WARNING`, do not raise
- [ ] On `SchemaError`: collector logs the field diff, continues to next symbol, does NOT write partial data to ArcticDB
- [ ] Validator skips empty bar lists silently
- [ ] Unit test: mock Bar with `volume=None` → `SchemaError` raised; fully valid Bar → passes

---

### QWS-1503 — CONTFUT Revision Detection

**Goal:** Detect when IBKR has silently re-adjusted historical CONTFUT prices and fix the `adjusted` metadata bug.

**Problem:** IBKR back-adjusts CONTFUT history on every new roll. Stored series silently diverges from a fresh fetch with no signal. Also: `adjusted = False` is currently written to bar metadata in `_bars_to_df()` for both CONTFUT and stitched FUT paths — this is factually wrong, as the data is ratio-adjusted.

**Implementation notes — adjusted flag fix (not a one-liner):**

`_bars_to_df()` at line 253 in `ibkr_futures.py` is shared by multiple call paths. The correct fix is to add `adjusted: bool = False` as a parameter:
- `_fetch_contfut()` calls `_bars_to_df()` → pass `adjusted=True`
- `_ratio_stitch()` returns the final stitched DataFrame → set `adjusted = True` on the result before returning
- `_fetch_contract_bars()` (individual contract fetches, pre-stitch) → continue using `adjusted=False`

The per-contract raw fetches are NOT adjusted — only the final stitched or CONTFUT output is.

**Implementation notes — revision detection:**

The CONTFUT incremental collect path has an early-return guard (`if last_bar >= now - timedelta(hours=1): return`). The revision comparison must run BEFORE this early-return check, because if the symbol is up to date, `_fetch_contfut()` is never called and the comparison never fires. Read stored data at the top of the CONTFUT branch regardless of the freshness check.

Comparison logic: `overlap = new_df.index.intersection(stored_df.index)` → compare `new_df.loc[overlap[0], 'close']` vs `stored_df.loc[overlap[0], 'close']`. Handle empty stored series (first seed) by skipping comparison and logging info.

**Deliverable:**
- `adjusted` parameter threaded through `_bars_to_df()` call chain as described above
- Revision check reads stored data at CONTFUT branch entry (before early-return); computes overlap and compares close at first overlapping bar AND last overlapping bar; warns if either delta > threshold
- Threshold: `contfut_revision_threshold: float = 0.005` in `data/config.py` `Settings`

**Files touched:** `data/collectors/ibkr_futures.py`, `data/config.py`

**Acceptance criteria:**
- [ ] `_bars_to_df()` accepts `adjusted: bool = False`; CONTFUT and stitched FUT paths pass `adjusted=True`; individual contract fetches pass `adjusted=False` (or rely on default)
- [ ] On CONTFUT collect, revision check fires even when incremental early-return would have skipped the fetch
- [ ] If no stored data (first seed): log `INFO "No stored CONTFUT data, skipping revision check"`, continue
- [ ] Warns (does not block, does not auto-reseed) if delta > threshold at first OR last overlapping bar
- [ ] Warning includes: symbol, fetch_date, stored_close, fetched_close, delta_pct, recommendation to full reseed
- [ ] Threshold read from `Settings.contfut_revision_threshold`; default 0.5%
- [ ] Test: synthetic DataFrames with 0.6% close delta at overlap → warns; 0.3% → logs only; empty stored → logs INFO, continues

**Note:** Must be implemented BEFORE QWS-1505 — both stories modify `ibkr_futures.py`. Implement and merge QWS-1503 first to avoid merge conflicts.

---

### QWS-1504 — Collector Delivery Monitor

**Goal:** Fast, cron-safe check that last night's data collection actually ran and delivered.

**Problem:** Prefect flows run overnight. No fast way to confirm collection succeeded before trusting bars in a research session. Researcher may run trials on stale data with no signal.

**Implementation notes:**
- Use `Store.get_symbol_info()` (see Infrastructure Note) — not `symbol_meta()` which does a full bar read; at 216+ symbols, `symbol_meta()` would take several minutes
- Enumerate `store.list_symbols('crypto')` + `store.list_symbols('futures')` — not `Settings.futures_symbols` (not all TFs may be seeded); skip `futures_meta`
- Expected bar spacing inferred from symbol key suffix (same as QWS-1501)
- STALE threshold: `last_update_time > 2 × expected_spacing` from now

**Deliverable:** `scripts/check_feeds.py`
- Enumerates all symbols in `crypto` + `futures` libs via `store.list_symbols()`
- Uses `Store.get_symbol_info()` for `last_update_time` without reading bar data
- Prints STALE/OK per feed: `symbol | tf | last_ts | expected | age | status`
- Non-zero exit on any STALE

**Files touched:** `scripts/check_feeds.py` (new), `data/store.py` (new `get_symbol_info()` if not already added by QWS-1501)

**Acceptance criteria:**
- [ ] Covers all symbols in `crypto` + `futures` libs; skips `futures_meta`
- [ ] STALE if `last_update_time` > 2× bar spacing from now
- [ ] Output table matches specified columns
- [ ] Non-zero exit on any STALE
- [ ] Runs in <15s for current symbol count (verified via `time`)
- [ ] `RESEARCH_WORKFLOW.md` `## Session Startup` section (added by QWS-1501) includes `python scripts/check_feeds.py` as the second startup command

---

### QWS-1505 — IBKR Roll Anomaly Alert

**Goal:** Block silent corruption of stitched futures series when a roll produces an extreme ratio.

**Problem:** `_ratio_stitch()` logs roll ratios but silently applies any value. A bad contract fetch (IBKR returns partial data for an expired contract) can produce a ratio of 0.1 or 10.0, which corrupts the entire stitched series.

**Implementation notes:**
- Guard applies to the **individual roll ratio** (`ratio = p_new / p_old`), NOT the cumulative ratio — the cumulative can legitimately be large from compounding
- `_ratio_stitch()` uses an endpoint fallback path when no overlap exists between contracts. On the fallback path, the ratio may look extreme due to contango/backwardation, not a data error. Log a prominent `WARNING` on the fallback path but do NOT raise `RollAnomalyError` — distinguish anomaly from expected price structure
- `RollAnomalyError(ValueError)` defined in `data/validation.py` alongside `SchemaError`
- Bounds: `roll_anomaly_min: float = 0.80` and `roll_anomaly_max: float = 1.20` in `data/config.py` `Settings`
- `RollAnomalyError` propagates through `_seed_stitched()` → `collect()` → caught by `collect_all()` `log.exception()` → Prefect flow marks task FAILED

**Deliverable:**
- `class RollAnomalyError(ValueError): pass` in `data/validation.py`
- In `_ratio_stitch()`: if `ratio` (individual roll) outside `[Settings.roll_anomaly_min, Settings.roll_anomaly_max]`, raise `RollAnomalyError` with: roll timestamp, p_old contract, p_new contract, computed ratio
- Fallback path: log `WARNING "Roll fallback path — no overlap; ratio may reflect contango/backwardation"` but do not raise

**Files touched:** `data/collectors/ibkr_futures.py`, `data/validation.py` (add `RollAnomalyError`), `data/config.py`

**Acceptance criteria:**
- [ ] `RollAnomalyError` importable from `data/validation.py`
- [ ] Individual roll ratio outside `[roll_anomaly_min, roll_anomaly_max]` raises `RollAnomalyError` with full context
- [ ] Cumulative ratio is never checked — only per-roll ratio
- [ ] Fallback path logs WARNING, does not raise
- [ ] `RollAnomalyError` propagates up; `collect_all()` logs it; Prefect flow marks FAILED
- [ ] Bounds read from `Settings`; defaults 0.80 / 1.20
- [ ] Test: synthetic frames with 25% individual roll gap → raises; 5% → logs ratio, continues; fallback path → WARNING logged, continues

**Note:** Implement AFTER QWS-1503 — both stories modify `ibkr_futures.py`.

---

### QWS-1510 — Data Steward Agent

**Goal:** Build the `data-steward` agent — the runtime owner of data layer health. Wires pre-flight health scripts into research session startup and covers Prefect incident triage.

**Problem:** Phase A ships `bar_health.py` and `check_feeds.py`, but nobody runs them. research-navigator's scope is `qw query` + graph reads; its guard does not allow python script execution. Without an owner for the data-layer pre-flight, the infrastructure ships and rots — exactly the failure mode the Two Sigma article warns against. Prefect-raised `SchemaError` / `RollAnomalyError` / CONTFUT drift warnings also have no roster owner.

**Blocked on:** QWS-1501 (bar_health.py must exist), QWS-1504 (check_feeds.py must exist)

**Deliverable:**

*Agent definition — `.claude/agents/data-steward.md`:*

Phase 1 — Session start gate:
- Run `python scripts/bar_health.py` and `python scripts/check_feeds.py`
- Parse exit codes and output
- If any P1 violation or STALE feed: surface to researcher with specific symbol/violation, recommend action (reseed, investigate collector), halt — do NOT proceed to research loop
- If clean: confirm "Data layer clean. N symbols verified." and hand off to research-navigator

Phase 2 — Incident triage (reactive):
- Diagnose Prefect-raised errors: `SchemaError` (Alpaca schema drift), `RollAnomalyError` (bad IBKR roll), CONTFUT revision warnings
- Read Prefect logs, identify root cause, propose fix or escalate to contractor-engineer with specific context
- Can write to `data/collectors/` and `data/validation.py` for minor schema contract updates
- Cannot touch: `strategies/`, `research/`, graph schema, champion lifecycle commands

*Guard script — `.claude/scripts/agent-data-guard.sh`:*
- ALLOW: `python scripts/bar_health.py`, `python scripts/check_feeds.py`, `qw query`, ArcticDB reads, Prefect log reads
- ALLOW writes to: `data/collectors/`, `data/validation.py`, `scripts/`
- BLOCK: `qw record --bundle`, `qw abort`, `qw degrade`, `qw retire`, `qw champion`, `qw monitor`, `qw promote`
- BLOCK: `python -m research.*` (not a trial runner)
- BLOCK: writes outside allowed paths
- BLOCK: `git commit`, `git push`

*research-navigator command file update:*
- Phase 1 of research-navigator must explicitly invoke data-steward as a pre-step before graph queries
- If data-steward exits non-zero (P1 violations or STALE feeds): research-navigator does not proceed to graph state synthesis

**Files touched:** `.claude/agents/data-steward.md` (new), `.claude/scripts/agent-data-guard.sh` (new), `.claude/agents/research-navigator.md` (update Phase 1), `docs/RESEARCH_WORKFLOW.md` (startup protocol section — this story completes what QWS-1501/1504 started)

**Acceptance criteria:**
- [ ] `.claude/agents/data-steward.md` exists with Phase 1 and Phase 2 defined
- [ ] `.claude/scripts/agent-data-guard.sh` enforces allow/block rules above
- [ ] research-navigator Phase 1 invokes data-steward before graph queries; halts if data-steward exits non-zero
- [ ] `RESEARCH_WORKFLOW.md` `## Session Startup` section is complete: data-steward invocation → bar_health.py + check_feeds.py → decision gate → research-navigator
- [ ] Manual test: introduce a P1 bar violation in ArcticDB (e.g. write a duplicate timestamp) → data-steward surfaces it, research session halts

---

## Phase B: Provenance Layer (Epic 15b)

*Depends on 15a being complete. All Phase B stories reference the correct module paths.*

### Correct Module Paths (Phase B)

The following paths are used throughout Phase B. These are the actual locations in the codebase:

| Epic spec may say | Correct path |
|---|---|
| `qws_graph/ingest.py` | `research/graph/store.py` — `GraphStore` class |
| `qws_graph/models.py` | `research/graph/models.py` — Pydantic models |
| Graph Cypher queries | `research/graph/cypher.py` |
| CLI commands | `research/graph/cli.py` |
| Trial bundle assembly | `research/trials/trial_base.py` — `make_bundle()`, `write_bundle()` |

The `qws_graph/` directory at project root exists but contains no Python source files. Do not create files there.

### Phase B Setup: BACKLOG_ALIGNMENT.md "Not Yet Implemented" Table

Before any Phase B story is implemented, update the "Not Yet Implemented" table in `BACKLOG_ALIGNMENT.md`:

Nodes to add: `DataSnapshot` (QWS-1506a), `InputSpec` (QWS-1507)
Edges to add: `CONSUMED_DATA` Run→DataSnapshot (QWS-1506b), `REQUIRES` Strategy→InputSpec (QWS-1507)
Properties to add: `data_as_of` on Run (QWS-1509), `python_version`/`pkg_lock_hash`/`random_seed` on Run (QWS-1508)

### Phase B Sprint Ordering

```
QWS-1506a (DataSnapshot node + hash)        — no deps
QWS-1506b (CONSUMED_DATA edge + preset)     — blocked on QWS-1506a
QWS-1507 (Input Contracts)                  — no deps; sequential before QWS-1508
QWS-1508 (Env Fingerprint)                  — after QWS-1507 (both touch research/graph/models.py + cypher.py)
QWS-1509 (Bitemporal as_of)                 — blocked on QWS-1506a
```

QWS-1507 and QWS-1508 both touch `research/graph/models.py` and `research/graph/cypher.py`. They must run sequentially within the sprint (on the same branch or with explicit merge gate).

---

### QWS-1506a — DataSnapshot Node + Hash

**Goal:** Define the `DataSnapshot` data structure and the content-hashing mechanism. First half of the foundational reproducibility story.

**Hash specification (locked):**
- Serialization: `hashlib.sha256(df.to_parquet()).hexdigest()` over the exact bar slice consumed by the trial
- Hash is purely content-based — NO timestamp in the hash input; same data must always produce same hash across concurrent ingests
- Cache: module-level dict `_snapshot_cache: dict[tuple[str, str, str, str], str]` keyed by `(lib, symbol, str(start), str(end))` in `data/store.py` — only useful within a single process; noted limitation

**Hash flow (trial → ingest):**
1. Trial script reads bars (e.g. `store.read_bars('futures', 'MES_1H', start=..., end=...)`)
2. Trial script writes `data_snapshots` block to `bundle.json` via updated `make_bundle()` — each entry: `{symbol, lib, timeframe, date_range_start, date_range_end}`; does NOT compute hash (trial script has no graph dependency)
3. `qw record --bundle` reads `data_snapshots` declarations, calls `Store.snapshot_id(lib, symbol, start, end)` per entry, computes hash; adds resolved hashes to bundle payload before graph write

**Neo4j constraint — one-time setup:**
`CREATE CONSTRAINT datasnapshot_content_hash IF NOT EXISTS FOR (n:DataSnapshot) REQUIRE n.content_hash IS UNIQUE`
This must run before Phase B goes live. Document as a one-time step in `research/graph/setup.py` or as a `qw seed` extension. Add to this story's AC.

**Deliverable:**
- `Store.snapshot_id(library, symbol, start, end) -> str` in `data/store.py` — reads bar slice, serializes via `.to_parquet()`, returns SHA-256 hex
- `Store.get_symbol_info(library, symbol)` in `data/store.py` — wraps `lib.get_description(symbol)`, returns SymbolDescription (if not already added by QWS-1501)
- `DataSnapshot` dataclass in `research/graph/models.py` with properties: `content_hash`, `symbol`, `lib`, `timeframe`, `date_range_start`, `date_range_end`, `snapshot_ts`, `row_count`
- `make_bundle()` in `research/trials/trial_base.py` gains optional `data_snapshots: list[dict] | None = None` parameter; writes `data_snapshots` block to `bundle.json`
- `docs/graph/data_dictionary.yaml` updated with `DataSnapshot` node definition

**Files touched:** `data/store.py`, `research/graph/models.py`, `research/trials/trial_base.py`, `docs/graph/data_dictionary.yaml`

**Acceptance criteria:**
- [ ] `Store.snapshot_id('futures', 'MES_1H', start, end)` returns a 64-char hex string
- [ ] Same bar data → same hash (stable across two calls within same process)
- [ ] Different bar data (post-reseed) → different hash
- [ ] `Store.get_symbol_info()` returns SymbolDescription without reading full bar data (verified: no `read_bars()` call in implementation)
- [ ] `make_bundle(data_snapshots=[...])` writes `data_snapshots` array to `bundle.json`
- [ ] `docs/graph/data_dictionary.yaml` contains `DataSnapshot` node with all properties
- [ ] Neo4j uniqueness constraint on `DataSnapshot.content_hash` documented in `research/graph/setup.py` as a setup step
- [ ] Performance: `Store.snapshot_id()` for a 2yr 1H series completes in <5s (verified via `time`)

---

### QWS-1506b — CONSUMED_DATA Edge + run_data_lineage Preset

**Goal:** Write `CONSUMED_DATA` edges from Run nodes to DataSnapshot nodes at ingest time, and expose the lineage via a query preset.

**Blocked on:** QWS-1506a

**Deliverable:**
- `DATA_SNAPSHOT_INGEST_QUERY` in `research/graph/cypher.py`: MERGE on `content_hash`, SET all DataSnapshot properties
- `CONSUMED_DATA_EDGE_QUERY` in `research/graph/cypher.py`: MERGE `(:Run {run_id: $run_id})-[:CONSUMED_DATA]->(:DataSnapshot {content_hash: $content_hash})`
- `GraphStore.write_data_snapshot(run_id: str, snapshots: list[DataSnapshot])` in `research/graph/store.py` — writes nodes + edges in a single transaction
- `_cmd_bundle()` in `research/graph/cli.py` — after CSV ingest, reads `data_snapshots` from manifest, calls `Store.snapshot_id()` per entry, calls `GraphStore.write_data_snapshot()`
- `qw record --bundle` fails (non-zero exit, stderr message) if ArcticDB read returns empty for a declared snapshot spec
- `run_data_lineage` preset in `research/graph/query_presets.py` — returns Run node + linked DataSnapshot hashes + symbol + date range
- `docs/PROVENANCE_ENGINE.md` gains `DataSnapshot` node section (properties, ID convention) and `CONSUMED_DATA` edge section

**Files touched:** `research/graph/cypher.py`, `research/graph/store.py`, `research/graph/cli.py`, `research/graph/query_presets.py`, `docs/PROVENANCE_ENGINE.md`

**Acceptance criteria:**
- [ ] `CONSUMED_DATA` edge exists in graph after `qw record --bundle` for any bundle with `data_snapshots` block
- [ ] Old bundles (no `data_snapshots` block) ingest cleanly — no error, no edge written
- [ ] `qw record --bundle` exits non-zero with clear stderr if declared symbol/range returns empty from ArcticDB
- [ ] `run_data_lineage` preset returns correct Run + snapshot data
- [ ] Test: reseed a symbol, re-ingest same trial → new DataSnapshot node written; original Run's `CONSUMED_DATA` edge still resolves to original snapshot hash (old node preserved)
- [ ] `PROVENANCE_ENGINE.md` DataSnapshot and CONSUMED_DATA sections complete with all properties and ID convention

---

### QWS-1507 — Strategy Input Contract

**Goal:** Each strategy declares its required ArcticDB symbols; `qw validate` enforces at trial time; graph records the dependency surface.

**Problem:** Strategies can silently pull any data. No declared dependency surface. Cannot answer "what strategies will break if we drop MNQ 1H?". Epic 12 feature engineering (QWS-1203) makes this worse — ML strategies consuming computed features with no declared inputs. Constraint for Epic 12: QWS-1203 (Feature Engineering Layer) must declare input contracts for all feature specs.

**Implementation notes — BaseStrategy extension:**

`BaseStrategy` has no `__init__`, no registry, and three unannotated class-level annotations (`name`, `markets`, `params`). The non-breaking extension pattern:

```python
from typing import ClassVar, NamedTuple

class InputContract(NamedTuple):
    symbol: str
    lib: str
    timeframe: str
    min_bars: int
    optional: bool = False

class BaseStrategy(ABC):
    ...
    input_contracts: ClassVar[list[InputContract]] = []
```

Each subclass that declares inputs overrides `input_contracts` as a class variable. Existing strategies inherit the empty list and pass `qw validate` silently (no declared inputs = no checks to fail).

**Implementation notes — qw validate --strategy:**

`qw validate --strategy <name>` is a **new argparse subparser** in `research/graph/cli.py`. It does not exist today. Implementation requires:
1. Add `validate` subparser to the CLI argument parser
2. Dynamic strategy import: import the module named in `strategies/<name>.py`, find the `BaseStrategy` subclass
3. Add `from data.store import get_store` import to `research/graph/cli.py` (currently absent — new cross-module dep)
4. For each `InputContract` in `strategy_class.input_contracts`: call `store.has_symbol(lib, symbol)` and `store.get_symbol_info(lib, symbol)` to verify min_bars

**Implementation notes — REQUIRES edge trigger:**

"Strategy registration" is an undefined concept in QWS. The `REQUIRES` edge is written during `qw record --bundle` when `input_contracts` data is present in `bundle.json`. Flow:
1. Trial script writes `input_contracts` block to `bundle.json` (serialized from the strategy class's `input_contracts` list)
2. `_cmd_bundle()` in `research/graph/cli.py` extracts `input_contracts` and calls new graph method to write `InputSpec` nodes + `REQUIRES` edges

**Implementation notes — InputSpec node:**

`InputSpec` is a separate node (not property set on Strategy). More queryable. Needs uniqueness constraint on composite key `(symbol, lib, timeframe)`. MERGE semantics: if same InputSpec already exists, just add the REQUIRES edge.

**Deliverable:**
- `InputContract` NamedTuple and `input_contracts: ClassVar[list[InputContract]] = []` in `strategies/base.py`
- `qw validate --strategy <name>` subparser in `research/graph/cli.py` with `data.store` import
- `InputSpec` node + `REQUIRES` edge Cypher in `research/graph/cypher.py`
- `GraphStore.write_input_contracts()` in `research/graph/store.py`
- `make_bundle()` gains `input_contracts` parameter; written to `bundle.json`
- `_cmd_bundle()` extracts `input_contracts` and calls `write_input_contracts()`
- `.claude/agents/trial-engineer.md` — Step 0b added to "Before Writing Any Trial": run `qw validate --strategy <name>`; BLOCKED output and halt on non-zero exit
- `docs/PROVENANCE_ENGINE.md` — InputSpec node + REQUIRES edge documented

**Files touched:** `strategies/base.py`, `research/graph/cli.py`, `research/graph/cypher.py`, `research/graph/store.py`, `research/trials/trial_base.py`, `docs/PROVENANCE_ENGINE.md`, `.claude/agents/trial-engineer.md`

**Acceptance criteria:**
- [ ] `InputContract` importable from `strategies/base.py`
- [ ] `qw validate --strategy <name>` exits non-zero if declared symbol not found in ArcticDB or has fewer bars than `min_bars`
- [ ] `qw validate --strategy <name>` exits 0 for strategies with empty `input_contracts` (no declared inputs → no checks → passes)
- [ ] `REQUIRES` edge written to graph after `qw record --bundle` for bundles with `input_contracts` block
- [ ] `InputSpec` node has uniqueness constraint on `(symbol, lib, timeframe)`
- [ ] trial-engineer agent has Step 0b; BLOCKED on validate failure
- [ ] `PROVENANCE_ENGINE.md` InputSpec node and REQUIRES edge sections complete
- [ ] Test: strategy declaring `{symbol: 'FAKE_1H', lib: 'futures', min_bars: 1000}` → `qw validate` exits non-zero

**Must run sequentially before QWS-1508 (shared files: `research/graph/models.py`, `research/graph/cypher.py`).**

---

### QWS-1508 — Environment Fingerprint on Run

**Goal:** Store python version, package lock hash, and random seed on every Run node so reproduction environment is documented.

**Implementation notes:**
- New Run properties must be `Optional[str] = None` — existing Run construction in tests must not break; backward-compatible with no `env` block in old bundles
- `pkg_lock_hash`: `hashlib.sha256(subprocess.run(['pip', 'freeze'], capture_output=True).stdout).hexdigest()` — if pip unavailable (conda env, restricted shell), fall back to hashing `pyproject.toml` contents only and log `WARNING "pip unavailable; pkg_lock_hash computed from pyproject.toml only"`
- `random_seed` is opt-in from `bundle.json` `env.random_seed` field; trial scripts that set a seed write it to bundle; trial scripts that don't are `None`
- Bundle flow: trial writes `env: {random_seed: <int_or_null>}` (or omits `env` block entirely); `qw record --bundle` fills in `python_version` + `pkg_lock_hash` at ingest time from current process; `random_seed` is merged from bundle if present
- `research/graph/cypher.py` `CSV_INGEST_QUERY` SET clause must be updated with null-safe properties for all three new Run fields
- Test isolation: mock `subprocess.run(['pip', 'freeze'], ...)` — do not actually run pip install in tests

**Deliverable:**
- `python_version: Optional[str] = None`, `pkg_lock_hash: Optional[str] = None`, `random_seed: Optional[str] = None` added to `Run` model in `research/graph/models.py`
- `_cmd_bundle()` in `research/graph/cli.py` populates `python_version` + `pkg_lock_hash` from current process before ingest; merges `random_seed` from bundle if present
- `CSV_INGEST_QUERY` SET clause updated in `research/graph/cypher.py`
- `env_drift` preset in `research/graph/query_presets.py` — finds Runs where `pkg_lock_hash` differs from the most recent Run's hash

**Files touched:** `research/graph/models.py`, `research/graph/cli.py`, `research/graph/cypher.py`, `research/graph/query_presets.py`

**Acceptance criteria:**
- [ ] `python_version`, `pkg_lock_hash`, `random_seed` written to Run node after `qw record --bundle`
- [ ] Old bundles (no `env` block) ingest cleanly with `None` for all three properties
- [ ] `pkg_lock_hash` is stable within same venv across multiple ingest calls (same process)
- [ ] `env_drift` preset returns Runs with differing `pkg_lock_hash`
- [ ] Unit test: mock `subprocess.run(['pip', 'freeze'])` returns known output → hash is deterministic; pip unavailable → WARNING logged, hash computed from pyproject.toml

---

### QWS-1509 — Bitemporal as_of on Runs

**Goal:** Record the data knowledge-time cutoff on every Run so vendor revisions cannot silently change backtest comparisons.

**Blocked on:** QWS-1506a (DataSnapshot nodes must exist; `as_of` anchors to snapshot timestamps)

**Implementation notes:**
- `data_as_of = max(snapshot.snapshot_ts for snapshots linked via CONSUMED_DATA)` — computed during ingest from linked DataSnapshot nodes; OR set explicitly from `bundle.json` `data_as_of` field if no snapshots (backwards compat path)
- Add `data_as_of: Optional[datetime] = None` to `Run` model in `research/graph/models.py`
- `stale_data_runs` preset threshold: `data_as_of < (run_ts - threshold_days)` — threshold configurable as preset parameter (default 30 days)
- Investigation required at kickoff: crypto collector does not currently emit `knowledge_time`. Databento pipeline does via `as_of`. Determine whether crypto collector needs a `collected_at` timestamp field added to bar metadata for QWS-1509 to be meaningful for crypto symbols.

**Deliverable:**
- `data_as_of: Optional[datetime] = None` on `Run` model in `research/graph/models.py`
- `_cmd_bundle()` in `research/graph/cli.py` computes `data_as_of` from linked DataSnapshot `snapshot_ts` values after ingest
- `stale_data_runs` preset with configurable threshold
- `CSV_INGEST_QUERY` SET clause updated for `data_as_of`

**Files touched:** `research/graph/models.py`, `research/graph/cli.py`, `research/graph/cypher.py`, `research/graph/query_presets.py`

**Acceptance criteria:**
- [ ] `data_as_of` written to Run node after ingest when DataSnapshot nodes exist
- [ ] Runs with no CONSUMED_DATA edges get `data_as_of = null` — no error
- [ ] `stale_data_runs` preset returns Runs where `data_as_of` is older than threshold before `run_ts`; example Cypher: `MATCH (r:Run) WHERE r.data_as_of < datetime() - duration({days: 30}) RETURN r LIMIT 10`
- [ ] Test: ingest Run with DataSnapshot timestamped 45 days before run_ts → appears in `stale_data_runs` at 30-day threshold

---

## Dependency Graph

```
Phase A (sprint):
  QWS-1501 ∥ QWS-1502 ∥ QWS-1504   — no shared files; parallel-safe
  QWS-1503 → QWS-1505               — both modify ibkr_futures.py; sequential
  QWS-1510                           — blocked on QWS-1501 + QWS-1504

Phase B (sprint):
  QWS-1506a (DataSnapshot node + hash)     — no deps; first
  QWS-1506b (CONSUMED_DATA edge + preset)  — blocked on QWS-1506a
  QWS-1507 (Input Contracts)               — no deps; sequential before QWS-1508
  QWS-1508 (Env Fingerprint)               — after QWS-1507 (shared files)
  QWS-1509 (Bitemporal as_of)              — blocked on QWS-1506a

Epic 12 (ML Research):
  QWS-1203 (Feature Engineering)           — must reference QWS-1507 Input Contracts in AC
  QWS-1201+ (ML harness)                   — runs against clean 15a+15b infrastructure
```

---

## The IBKR Ratio-Adjusted Price Problem (Standing Decision)

**Do not write a story to "fix" IBKR ratio-adjusted prices.**

IBKR CONTFUT is ratio-adjusted. This is not a bug to fix — it is a limitation to document and constrain around.

**Why not fix it now:**
- There is no fix that doesn't require an unadjusted price feed stored alongside, doubling storage and adding join complexity per symbol
- No current Champion requires absolute price levels — all are return-based
- Ratio adjustment preserves percentage returns — backtests are valid for return-based strategies

**What this limitation affects:**
- Dollar P&L anchored to historical levels — not currently used
- Spread analysis crossing adjustment epochs — not currently implemented
- Absolute price regime conditioning (e.g. "CL > $80") — Epic 12 must avoid

**Decisions made:**
1. QWS-1503 fixes the `adjusted = False` metadata bug by threading `adjusted: bool` through `_bars_to_df()` call chain
2. QWS-1203 (Feature Engineering, Epic 12) must explicitly prohibit price-level features from CONTFUT; use return-based features only — add to QWS-1203 acceptance criteria
3. A true point-in-time unadjusted price series is a valid future epic, but only if a champion requiring absolute price levels is promoted. That gate doesn't exist yet.

---

## Existing Run Node Migration (Standing Non-Decision)

Runs created before QWS-1506a will have no `CONSUMED_DATA` edge and no `DataSnapshot`. `data_as_of` (QWS-1509) will be null for all historical Runs. `stale_data_runs` and `run_data_lineage` presets will silently return no results for historical Runs.

**Decision: do not backfill.** Historical Runs cannot be retroactively snapshotted — the bar data they consumed may have been reseeded since then (the snapshot would be wrong). The correct posture is to treat pre-Epic-15 Runs as "un-reproducibility-verified" and move forward. Document this in `docs/PROVENANCE_ENGINE.md`.

---

## Sequencing Rationale

**Why not fold into Epic 14 or ML Research:**

Epic 14 is Research Pipeline Hardening — sharpening the research loop (annual P&L, regime diversity gate, ATR labels, Cypher bugfix). Different domain. Epic 14 closes with QWS-1406.

Epic 12 ML Research introduces volume (50+ Runs, feature engineering, walk-forward harness). Provenance infrastructure retrofitted after ML volume lands is expensive and incomplete — old Runs cannot be retroactively snapshotted.

**Why 15a before 15b:**

DataSnapshot (QWS-1506a) over unvalidated data is provenance-of-garbage. Run bar health audit (QWS-1501) and confirm clean data before snapshotting it. Input contracts (QWS-1507) are more meaningful once vendor schema validation (QWS-1502) is enforced at the collector layer.

**The QWS-0702 conflict:**

QWS-0702 (CI Graph Integrity Gate, unscheduled backlog) was designed to run 5 static graph integrity checks on every push. If Epic 15 lands first, the correct CI artifact is `qw validate` — data contracts running on push — not just graph structure. Do not build QWS-0702 in isolation and then retrofit contract validation. Hold QWS-0702 until Epic 15 scoping is decided.

---

## Risks

| Risk | Mitigation |
|---|---|
| DataSnapshot hash perf | Use `(lib, symbol, start, end)` cache dict in `data/store.py`; note: cache only lives within single process |
| `df.to_parquet()` requires pyarrow | `pyarrow` is already a transitive dep via ArcticDB; verify with `python -c "import pyarrow"` before QWS-1506a kickoff |
| QWS-1502 (Alpaca schema) breaks existing collection | Unknown extra fields log WARNING, do not raise — backwards safe |
| as_of (QWS-1509) needs collectors to emit knowledge_time | Crypto collector does not currently emit; investigate at QWS-1509 kickoff before committing to story |
| Adjusted flag fix (QWS-1503) scoped wrong | Fix requires function signature change, not one line; account for this in story sizing |
| Phase A ships without Phase B = false confidence | Data health (15a) + provenance (15b) must both ship to be meaningful. 15a alone does not mean the data layer is "fixed." |
| `qw validate` as new CLI subparser touches cli.py | cli.py is heavily used; test the existing subcommands after adding `validate` |

---

## Open Architectural Questions (Deferred)

**Data Vintage Library:**
Full ArcticDB snapshot-per-seed using `vintage key = {symbol}@{yyyymmdd_hhmm}` with `read_bars(as_of=...)` API. More powerful than DataSnapshot node approach but requires store.py refactor. Deferred — QWS-1506a delivers 80% of the value at 20% of the cost.

**Ratio Ledger:**
Persist roll ratios in `futures_meta` lib as `{root}_rolls` with `(roll_ts, p_old, p_new, ratio, cum_ratio)`. Stitch reuses ledger; only recomputes on new roll. Eliminates ratio-adjust drift entirely. Load-bearing change — must ship with reseed + backtest-diff report. Not scoped.

**Feature Store Layer:**
New ArcticDB `features` lib. Feature = pure function of `(DataSnapshot, params) → DataFrame`. `(:Run)-[:CONSUMED_FEATURE]->(:Feature)`. Revisit post Epic 12 when feature sharing pattern becomes clear. Not scoped now.

**Statistical Anomaly Block on Write:**
Write path runs z-score vs rolling baseline; `--force` flag required to override. Depends on rolling baseline infrastructure not yet built. Not scoped.

**Schema Migration Log:**
`docs/graph/migrations/` dir, one file per schema change tied to story ID. Not scoped — low urgency while schema is stable and Will is sole contributor.
