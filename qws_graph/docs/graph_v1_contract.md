# Graph V1 Contract

## Overview and Scope

This document is the implementation contract for Graph V1 in `QuantWorkstation`.

V1 objective:
- Keep current research execution unchanged.
- Ingest existing artifacts into Neo4j as a relational ledger.
- Make ingestion deterministic, idempotent, and auditable.

V1 architecture:
- Files are the source of work.
- Graph is the source of truth for research direction and lineage.
- `qw record` is the first integration surface.
- Existing shell scripts remain execution entrypoints.

In-scope for V1:
- Artifact ingestion for baseline CSV, grid CSV, champion Markdown.
- Deterministic IDs + idempotent MERGE writes.
- Offline mode with pending queue.
- Receipts and reconcile/query CLI surface.

Out-of-scope for V1:
- MCP write path.
- VS Code HUD/CodeLens.
- Live-instance drift monitoring.
- Rich `tracker.md` structural parsing.

---

## Risk Model and Guardrails

### Data integrity
- IDs are deterministic from normalized payloads.
- Writes use one transaction per artifact via `UNWIND + MERGE`.
- Manual Neo4j edits can bypass validation (accepted power-user risk).

Guardrails:
- Pydantic validation required before persistence.
- Provenance fields required on every node written from artifact data.
- Round-trip hash validation required in tests.

### Workflow disruption
- Shell hooks must soft-fail: `qw record ... || true`.
- Neo4j connection timeout is 3 seconds.
- `qw record` defaults to online mode; offline is explicit via `--offline`.
- Script outputs and CLI flags must not be changed in V1.

### Schema design
- Pydantic model config uses `extra='ignore'` in V1.
- Unknown fields are logged in `qw record` output.
- Missing required fields fail validation.

### Operational complexity
- `--offline` mode required.
- If offline, validated payload is written to `.qws/pending/`.
- Research execution must continue even if Neo4j is unavailable.

### Testing and validation
- Golden fixtures required under `tests/fixtures/artifacts/`.
- Parser regression tests required for all artifact types.
- Parser module target is full coverage.

### Scope guardrails
- No MCP/HUD code merge until `qw record` + `qw reconcile` are stable on main.

---

## Artifact Types in V1

Canonical artifact kind enum for `ResearchArtifact.kind`, `qw record --kind`, pending payloads, and receipts:

| Kind | Source format | Expected location pattern | V1 ingest behavior |
|---|---|---|---|
| `baseline_csv` | CSV | `results/*_baseline.csv` | Parse rows, write `Strategy` + `Run` + `Config` |
| `grid_csv` | CSV | `results/*_grid_*.csv` | Parse rows, write `Strategy` + `Run` + `Config` |
| `champion_md` | Markdown | `research/results/champions/*.md` | Parse document, write `Champion`, link to `Strategy`, optional pivot |
| `tracker_md` | Markdown | `research/*tracker*.md` | Attach raw blob metadata only (`BlobArtifact`) |

### 1) Baseline CSV
Expected examples:
- `results/es_bear_baseline.csv`
- `results/nq_bear_baseline.csv`

V1 treatment:
- One `Run` node per ingested row.
- One `Config` node connected to each run.
- One `Strategy` node connected to each run.

### 2) Grid CSV
Expected examples:
- `results/es_bear_sweep_1h_grid_*.csv`
- `results/nq_bear_sweep_1h_grid_*.csv`

V1 treatment:
- Same as baseline CSV ingestion.
- Additional lineage edge support for champion promotion if champion refers to grid source.

### 3) Champion Markdown
Expected examples:
- `research/results/champions/es_bear_sweep_1h_v1.md`
- `research/results/champions/nq_bear_sweep_1h_v1.md`

V1 treatment:
- One `Champion` node.
- Connected to `Strategy`.
- Connected to source `Run`/`Config` where resolvable.
- Optional pivot edge from `--pivot-from <run_id>`.

### 4) Tracker markdown (raw attachment only)
- `research/es_nq_bear_sweep_tracker.md` is not strict-structured in V1.
- It may be attached as `BlobArtifact` metadata only.
- No pivot extraction from tracker text in V1.

---

## Canonical ID Strategy

### Normalization rules
Apply before hashing:
1. Lowercase.
2. Strip leading/trailing whitespace.
3. Replace spaces and underscores with `-`.
4. Remove characters outside `[a-z0-9-]`.
5. Collapse repeated `-`.
6. For dicts: sort keys recursively before JSON serialization.

### Hash algorithm
- SHA-256.
- Truncate to first 12 hex characters.
- Example: `a1b2c3d4e5f6`.

### Collision handling
- Fail-fast with `CriticalIDError`.
- No automatic fallback ID generation in V1.
- Collision condition: if a deterministic ID already exists but resolves to a different canonical payload hash, abort write and return validation failure semantics for that artifact.
- `CriticalIDError` is terminal for that `qw record` invocation and must not emit partial graph writes.

### Reference implementation (contract code)
```python
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class CriticalIDError(RuntimeError):
    pass


def normalize_text(value: str) -> str:
    s = value.strip().lower().replace("_", " ")
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash12(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def strategy_id(instrument: str, timeframe: str, direction: str, logic_type: str) -> str:
    slug = "-".join(
        [
            normalize_text(instrument),
            normalize_text(timeframe),
            normalize_text(direction),
            normalize_text(logic_type),
        ]
    )
    return slug


def run_id(strategy_id_value: str, artifact_path: str, artifact_mtime_iso: str) -> str:
    return hash12(strategy_id_value, normalize_text(artifact_path), artifact_mtime_iso)


def config_id(params: dict[str, Any], risk_params: dict[str, Any]) -> str:
    return hash12(canonical_json(params), canonical_json(risk_params))


def champion_id(strategy_id_value: str, freeze_date_iso: str) -> str:
    return hash12(strategy_id_value, freeze_date_iso)
```

---

## V1 Schema Definitions (Pydantic-level)

Runtime assumptions:
- Python `>=3.11`
- Pydantic v2

Model policy:
- `extra='ignore'` for V1.
- Unknown fields logged by CLI.

```python
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict


class Provenance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    artifact_path: str
    artifact_hash: str
    artifact_mtime_iso: str
    ingested_at: datetime
    parser_version: str = "v1"


class Strategy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    instrument: str
    timeframe: str
    direction: Literal["long", "short", "bear", "bull"]
    logic_type: str
    # Added in Story 1 (Churn):
    family_id: str | None = None        # hash12(logic_type, direction, source_hash)
    # Graph-only (set by `qw abort`; not persisted during CSV ingest):
    # status: str | None          — "ABORTED" when marked dead
    # abort_reason: str | None    — mandatory reason string for abort
    # aborted_at: datetime | None — timestamp of abort decision


class Config(BaseModel):
    model_config = ConfigDict(extra="ignore")

    config_id: str
    params_json: dict[str, Any]
    risk_params: dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    strategy_id: str
    timestamp: datetime
    sharpe: float
    profit_factor: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    total_r: float | None = None
    artifact_path: str          # repo-relative POSIX path (e.g. research/results/.../baseline.csv)
    provenance: Provenance
    # Graph-only properties (set by store.py; not in the parsed payload):
    # evidence_score: float       — sharpe × √total_trades; computed at write time
    # was_best: bool (REMOVED)    — renamed to peaked_as_best in this repo
    # peaked_as_best: bool | None — true when this run was displaced from Strategy.best_run_id;
    #                               permanent provenance flag, never cleared; absent if never best

    @field_validator("win_rate")
    @classmethod
    def win_rate_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("win_rate must be in [0,1]")
        return v


class Champion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    champion_id: str
    strategy_id: str
    freeze_date: date
    metrics_summary: dict[str, float | int | str]
    oos_status: str
    fragilities: list[str]
    artifact_path: str
    pivot_from_run_id: str | None = None
    provenance: Provenance


class BlobArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    artifact_path: str
    artifact_kind: Literal["tracker_md"]
    raw_text_sha256: str
    provenance: Provenance


class ResearchArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["baseline_csv", "grid_csv", "champion_md", "tracker_md"]
    strategy: Strategy
    runs: list[Run] = Field(default_factory=list)
    configs: list[Config] = Field(default_factory=list)
    champion: Champion | None = None
    blob: BlobArtifact | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ResearchArtifact":
        if self.kind in {"baseline_csv", "grid_csv"} and not self.runs:
            raise ValueError("CSV artifacts require at least one run")
        if self.kind == "champion_md" and self.champion is None:
            raise ValueError("champion_md requires champion payload")
        if self.kind == "tracker_md" and self.blob is None:
            raise ValueError("tracker_md requires blob payload")
        return self
```

### Example payloads

#### Strategy
```json
{
  "strategy_id": "es-1h-bear-bear-baseline",
  "instrument": "ES",
  "timeframe": "1H",
  "direction": "bear",
  "logic_type": "bear-baseline"
}
```

#### Run
```json
{
  "run_id": "a1b2c3d4e5f6",
  "strategy_id": "es-1h-bear-bear-baseline",
  "timestamp": "2026-04-02T12:30:00Z",
  "sharpe": 1.3749,
  "profit_factor": 1.1562,
  "win_rate": 0.3737,
  "max_drawdown": -8.686,
  "total_trades": 99,
  "total_r": 10.1601,
  "artifact_path": "results/es_bear_sweep_1h_grid_nypre_london_v1.csv",
  "provenance": {
    "artifact_path": "results/es_bear_sweep_1h_grid_nypre_london_v1.csv",
    "artifact_hash": "<sha256>",
    "artifact_mtime_iso": "2026-04-02T12:30:00Z",
    "ingested_at": "2026-04-02T12:31:10Z",
    "parser_version": "v1"
  }
}
```

#### Champion
```json
{
  "champion_id": "0ab1cd2ef345",
  "strategy_id": "es-1h-bear-bear-baseline",
  "freeze_date": "2026-04-02",
  "metrics_summary": {
    "sample_size": 99,
    "sharpe": 1.374947,
    "profit_factor": 1.15625,
    "max_drawdown_r": -8.68605
  },
  "oos_status": "oos_pending",
  "fragilities": [
    "session-dependent edge",
    "slippage sensitivity"
  ],
  "artifact_path": "research/results/champions/es_bear_sweep_1h_v1.md",
  "pivot_from_run_id": "a1b2c3d4e5f6",
  "provenance": {
    "artifact_path": "research/results/champions/es_bear_sweep_1h_v1.md",
    "artifact_hash": "<sha256>",
    "artifact_mtime_iso": "2026-04-02T13:00:00Z",
    "ingested_at": "2026-04-02T13:01:00Z",
    "parser_version": "v1"
  }
}
```

---

## Graph Write Semantics for `qw record`

### Execution mode
- V1 is synchronous only.
- No background queue worker in V1.

### Default mode
- Default is online graph write.
- `qw record` attempts a Neo4j handshake with a 3-second timeout.
- If handshake fails and `--offline` is not set:
  - print `WARNING` with failure summary
  - print retry guidance (`start Neo4j` or rerun with `--offline`)
  - exit with code `2`

### Offline mode
- `--offline` skips Neo4j network calls.
- Validated payload written to `.qws/pending/<artifact_id>.json`.
- Exit code is `0` on successful validation + pending write.

### Exit codes
- `0`: validation passed and persisted, or validation passed and written to pending in offline mode.
- `1`: schema validation failure.
- `2`: infrastructure failure (Neo4j unavailable and `--offline` not provided).
- `--dry-run` returns `0` only when parse + validation succeed; it writes neither pending payloads nor receipts.

### Receipt behavior
For every successful non-dry-run `qw record` call, write a receipt JSON to `.qws/receipts/<run_or_champion_id>.json`.

Write mode matrix:
- Online success: graph write + receipt, no pending file.
- Offline success (`--offline`): pending file + receipt with `status=pending_offline`.
- Validation failure: no graph write, no pending file, no receipt.
- Infra failure (`--offline` not set): no graph write, no pending file, no receipt.
- Dry-run success: no graph write, no pending file, no receipt.

Required receipt fields:
- `id`
- `kind`
- `artifact_path`
- `artifact_hash`
- `status` (`persisted` or `pending_offline`)
- `ingested_at`
- `node_counts`
- `relationship_counts`
- `warnings`

### `.qws/` layout
```text
.qws/
  receipts/
    <id>.json
  pending/
    <id>.json
  logs/
    qw.log
```

Retention policy:
- Keep last 1000 receipts or 30 days, whichever is smaller.

---

## Provenance and Idempotency Rules

### Provenance requirements
Each ingested node created from artifact data must include:
- source artifact path
- source artifact hash
- source mtime
- ingestion timestamp
- parser version

### Idempotency keys
- `Strategy`: `strategy_id`
- `Run`: `run_id`
- `Config`: `config_id`
- `Champion`: `champion_id`

### MERGE pattern
- MERGE nodes first by PK.
- SET mutable fields with last-write-wins from the artifact.
- MERGE relationships with deterministic endpoints only.

### Duplicate prevention rule
Re-running `qw record` against unchanged artifact must:
- produce zero additional nodes
- produce zero additional relationships
- update receipt only

---

## Cypher Mappings (V1)

The following statements are contract-level references for implementation.

### Ingest strategy + runs + configs (CSV)
Applies to both `baseline_csv` and `grid_csv` payloads.

```cypher
UNWIND $rows AS row
MERGE (s:Strategy {strategy_id: row.strategy.strategy_id})
  ON CREATE SET
    s.instrument = row.strategy.instrument,
    s.timeframe = row.strategy.timeframe,
    s.direction = row.strategy.direction,
    s.logic_type = row.strategy.logic_type,
    s.created_at = datetime()
  SET
    s.updated_at = datetime()

MERGE (r:Run {run_id: row.run.run_id})
  ON CREATE SET
    r.created_at = datetime()
  SET
    r.timestamp = datetime(row.run.timestamp),
    r.sharpe = row.run.sharpe,
    r.profit_factor = row.run.profit_factor,
    r.win_rate = row.run.win_rate,
    r.max_drawdown = row.run.max_drawdown,
    r.total_trades = row.run.total_trades,
    r.total_r = row.run.total_r,
    r.artifact_path = row.run.artifact_path,
    r.artifact_hash = row.run.provenance.artifact_hash,
    r.artifact_mtime_iso = row.run.provenance.artifact_mtime_iso,
    r.ingested_at = datetime(row.run.provenance.ingested_at),
    r.parser_version = row.run.provenance.parser_version,
    r.updated_at = datetime()

MERGE (c:Config {config_id: row.config.config_id})
  ON CREATE SET
    c.created_at = datetime()
  SET
    c.params_json = row.config.params_json,
    c.risk_params = row.config.risk_params,
    c.updated_at = datetime()

MERGE (s)-[:HAS_RUN]->(r)
MERGE (r)-[:USES_CONFIG]->(c)
```

### Ingest champion markdown
Applies to `champion_md` payloads.

```cypher
MERGE (s:Strategy {strategy_id: $champion.strategy_id})
  ON CREATE SET s.created_at = datetime()
  SET s.updated_at = datetime()

MERGE (ch:Champion {champion_id: $champion.champion_id})
  ON CREATE SET ch.created_at = datetime()
  SET
    ch.freeze_date = date($champion.freeze_date),
    ch.metrics_summary = $champion.metrics_summary,
    ch.oos_status = $champion.oos_status,
    ch.fragilities = $champion.fragilities,
    ch.artifact_path = $champion.artifact_path,
    ch.artifact_hash = $champion.provenance.artifact_hash,
    ch.artifact_mtime_iso = $champion.provenance.artifact_mtime_iso,
    ch.ingested_at = datetime($champion.provenance.ingested_at),
    ch.parser_version = $champion.provenance.parser_version,
    ch.updated_at = datetime()

MERGE (s)-[:PRODUCED_CHAMPION]->(ch)

FOREACH (_ IN CASE WHEN $pivot_from_run_id IS NULL THEN [] ELSE [1] END |
  MERGE (r:Run {run_id: $pivot_from_run_id})
  MERGE (ch)-[:PIVOTED_FROM]->(r)
)
```

### Attach tracker as raw blob
```cypher
MERGE (s:Strategy {strategy_id: $blob.strategy_id})
MERGE (b:BlobArtifact {artifact_path: $blob.artifact_path})
  ON CREATE SET b.created_at = datetime()
  SET
    b.artifact_kind = $blob.artifact_kind,
    b.raw_text_sha256 = $blob.raw_text_sha256,
    b.artifact_hash = $blob.provenance.artifact_hash,
    b.ingested_at = datetime($blob.provenance.ingested_at),
    b.updated_at = datetime()
MERGE (s)-[:HAS_BLOB]->(b)
```

### Significance Gate (grid_csv only)

Applies to `grid_csv` artifacts. Introduced in Story 1 (Churn epic).

Default: `qw record --kind grid_csv` selects up to 7 instructive runs from the full CSV
and rolls the remainder into one `RunStatsSummary` node.

**Selection tiers (applied in order, non-overlapping):**

| Tier | Criterion | Default N |
|---|---|---|
| Performance | Top N rows by `sharpe` | 5 |
| Risk boundary | Bottom N rows by `max_drawdown` (most negative = worst) | 2 |
| Provenance | Rows whose `run_id` matches a known champion's `pivot_from_run_id` | all |
| Manual override | `--significant <run_id>` flag at `qw record` time | all |

`--all` flag bypasses the gate entirely (existing behaviour preserved).
`baseline_csv` is unaffected.

### RunStatsSummary Node

Aggregate record for grid-sweep rows that did not pass the significance gate.

```
RunStatsSummary {
    summary_id: str            # hash12(strategy_id, artifact_path, artifact_mtime_iso)
    strategy_id: str
    artifact_path: str
    total_run_count: int
    selected_run_count: int
    rolled_up_run_count: int
    sharpe_mean: float
    sharpe_max: float
    sharpe_min: float
    max_drawdown_worst: float  # most negative value = worst
    ingested_at: datetime
}
```

Edge: `(Strategy)-[:HAS_RUN_SUMMARY]->(RunStatsSummary)`

Merged idempotently on `summary_id`; when the same CSV is re-ingested after modification
(mtime changes) a new `summary_id` is generated and a new node is created.

### OOS Outcome Update Contract (QWS-0402 + QWS-0402C)

`qw record --oos <status> --champion <id> [--sharpe <float>]` updates properties on
the `Champion` node via `update_champion_oos_status()`:

```
Champion.oos_status       = "oos_pass" | "oos_fail" | "oos_pending"
Champion.oos_date         = date()     — ISO date of the update (today by default)
Champion.metrics_oos_sharpe = <float>  — set when --sharpe is provided; otherwise unchanged
```

These properties are **never written by the champion ingest path** (`CHAMPION_INGEST_QUERY`).
Re-ingesting a champion markdown does not touch `oos_date` or `metrics_oos_sharpe`.

Valid `oos_status` values:
- `oos_pending` — default; no OOS validation performed yet
- `oos_pass` — OOS validation passed
- `oos_fail` — OOS validation failed

`--sharpe` is optional. When absent, `metrics_oos_sharpe` remains null (backwards-compatible).
When present, must be non-negative (negative values rejected with exit code 1).

Migration note: nodes carrying the old enum values (`live_paper`, `retired`) from
pre-QWS-0402 ingest are handled at write time:
- `live_paper` → allowed to be updated (forward-tested; treated as validated)
- `retired` → rejected with a lifecycle error; use `qw retire` for lifecycle transitions

A receipt with `kind: oos_update` and `status: persisted` is written on success.
The receipt includes an `oos_sharpe` key: float when `--sharpe` was provided, null when absent.

### ResearchTarget Singleton Contract (QWS-0408)

`qw seed --targets` creates or updates the singleton `ResearchTarget` node via
`ensure_research_target()`. The node is identified by the fixed property `target_id = "singleton"`.

Seeding Cypher (abbreviated):
```cypher
MERGE (rt:ResearchTarget {target_id: "singleton"})
ON CREATE SET
  rt.sharpe_professional = 2.0,
  rt.sharpe_institutional = 3.5,
  rt.max_holding_hours = 4,
  rt.min_trades = 30,
  rt.min_active_window_frequency = 0.06,
  rt.profit_factor_min = 1.3,
  rt.calmar_min = 1.5,
  rt.max_drawdown_floor = -0.20,
  rt.correlation_gate = 0.30,
  rt.created_at = datetime()
SET rt.updated_at = datetime()
```

Override (applied after seed in the same transaction when `--set` flags are provided):
```cypher
MATCH (rt:ResearchTarget {target_id: "singleton"})
SET rt += $overrides
```

Exit codes for `qw seed --targets`:
- `0`: node seeded or already current
- `1`: unknown `--set` key
- `2`: Neo4j unavailable

`qw query --name research_targets` returns all properties via `get_research_targets_v1()`.
Empty result means the node has not yet been seeded — run `qw seed --targets` first.

The `standards.py` enforcement logic is **not** updated by this contract — the graph node
is the read surface only. Changing promotion thresholds still requires a code change to
`standards.py` in addition to updating the graph node.

### Hypothesis Journaling Contract (QWS-0601)

`qw record --hypothesis "<title>"` creates a Hypothesis node and SUGGESTED edge.

```
Hypothesis.hypothesis_id = hash12(title, created_at_iso)
Hypothesis.title         = <title>
Hypothesis.status        = "open"
Hypothesis.created_at    = datetime()
Hypothesis.updated_at    = datetime()
SUGGESTED.source         = "user"
```

Additional modes:
- `qw record --hypothesis <id> --tested-as <strategy_id>` → TESTED_AS edge
- `qw record --hypothesis <id> --branched-from <node_id> --rationale "<text>"` → BRANCHED_FROM edge
- `qw record --hypothesis <id> --status confirmed|refuted|abandoned|open` → update status

Valid status values: `open`, `confirmed`, `refuted`, `abandoned`.

MCP write tool `log_hypothesis(title)` creates a Hypothesis with `source="llm"` on the SUGGESTED edge.

Query presets:
- `list_hypotheses` — all Hypothesis nodes ordered by `created_at` DESC
- `hypothesis_audit --param hypothesis_id=<id>` — linked strategies, runs, outcomes, champions
- `check_redundancy --param hypothesis_id=<id>` — title substring match against active champions and aborted strategies; also surfaces SEMANTICALLY_RELATED hypotheses when edges exist
- `similar_hypotheses --param hypothesis_id=<id>` — hypotheses with SEMANTICALLY_RELATED edges, ordered by similarity DESC

Exit codes for `qw record --hypothesis`:
- `0`: success
- `1`: validation error or referenced node not found
- `2`: Neo4j unavailable

### Semantic Hypothesis Deduplication Contract (QWS-0604)

On each `qw record --hypothesis "<title>"` call (create mode):
1. Hypothesis node is created (as before).
2. Title is embedded using `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU, local).
3. Embedding vector stored as `Hypothesis.embedding: list[float]`.
4. All existing Hypothesis nodes with stored embeddings are loaded.
5. Cosine similarity computed against each existing embedding.
6. `SEMANTICALLY_RELATED` edges MERGED for pairs with `similarity >= threshold` (default 0.85).
7. If N similar hypotheses found: CLI prints advisory message with the `qw query --name similar_hypotheses` command.

```
Hypothesis.embedding = [float, ...]   # 384-dim vector, set at creation
SEMANTICALLY_RELATED.similarity      = <cosine score>
SEMANTICALLY_RELATED.pair_key        = sorted(id_a, id_b) joined with "|"
SEMANTICALLY_RELATED.computed_at     = datetime()
```

Symmetric: A→B and B→A edges are written with the same `similarity` value.

Override threshold: `qw record --hypothesis "<title>" --similarity-threshold 0.90`

Backfill for pre-existing hypotheses: `qw backfill --embeddings`
- Computes and stores embedding for every Hypothesis node with null `embedding`.
- Creates missing `SEMANTICALLY_RELATED` edges across all pairs.
- Exit code 0 on completion; 1 when sentence-transformers not installed; 2 when Neo4j unavailable.

Embedding failures (ImportError, model load error) are non-fatal for `qw record --hypothesis`:
the hypothesis node is created successfully and a WARNING is printed to stderr.

### Abort Strategy Contract

`qw abort --strategy <strategy_id> --reason "<reason>"` sets three graph-only properties
on the `Strategy` node via `ABORT_STRATEGY_QUERY`:

```
Strategy.status      = "ABORTED"
Strategy.abort_reason = <reason>
Strategy.aborted_at  = datetime()
```

These are `SET` operations — no data is deleted. `get_strategy_summary_v1` returns
`status` and `abort_reason` in its output. `--reason` is mandatory and must be non-empty.

---

## Phase Boundaries for "Graph as Truth"

### Phase 1 (Sidecar)
- Files are authoritative for all numeric outputs and workflow state.
- Graph mirrors structured lineage.

### Phase 2 (Index)
- Files remain authoritative for raw metrics.
- Graph authoritative for relationships and pivot lineage.

### Phase 3 (Primary)
- Graph authoritative for decision state (promotion/OOS readiness).
- Files become exports and audit artifacts.

---

## MCP Read Contract (V1)

Policy: Neo4j-only reads.

MCP assumptions in V1:
- If data is not in graph, MCP does not see it.
- MCP does not parse local files directly.
- MCP reads only approved node/edge set from this contract.

No MCP write in V1.

### Neighborhood Bounding (V1 Safety Cap)

`get_context_neighborhood` fans out to four view functions and returns a bounded result:

```
get_champion_details_v1(champion_id)     → champion
get_strategy_summary_v1(strategy_id)    → strategy
get_config_linkage_v1(pivot_from_run_id) → pivot_config (if present)
get_run_history_v1(strategy_id)         → recent_runs (capped at max_runs)
```

Response shape:
```json
{
  "champion":     { ... },
  "strategy":     { ... },
  "pivot_config": { ... } | null,
  "recent_runs":  [ ... ],
  "runs_capped":  true | false
}
```

`max_runs` default: 50. Upper bound: 200. Values outside 1–200 return `INVALID_PARAMS`.
When the strategy has more runs than `max_runs`, `runs_capped` is `true`.
`get_run_history_v1` must be registered in `QUERY_VIEW_REGISTRY` before this contract can be satisfied end-to-end.

### Portfolio Correlation Contract (QWS-0603)

`python -m research.analytics.portfolio_correlation [--threshold 0.6]` computes pairwise
Pearson correlation across OOS-pass Champions and writes `CORRELATED_WITH` edges to the graph.

```
CORRELATED_WITH (Champion)-[CORRELATED_WITH]->(Champion)
CORRELATED_WITH (Strategy)-[CORRELATED_WITH]->(Strategy)
```

Properties written:
```
coefficient:  float   — Pearson r
threshold:    float   — threshold used during computation
lookback:     str     — "full" or descriptive window label
pair_key:     str     — sorted(id_a, id_b) joined with pipe (dedup key)
computed_at:  datetime
```

Symmetric: each pair written in both A→B and B→A directions.
Idempotent: `MERGE ... {pair_key: ...}` prevents duplicates.

Correlation gate in `qw record --bundle`:
After an auto-promote event, `check_correlated_with_active_champions()` queries for
existing `CORRELATED_WITH` edges on the new Champion. If any exist above threshold (0.60
default), a non-blocking `CORRELATION WARNING` is printed to stderr.

`portfolio_alpha` preset extended columns (QWS-0603):
- `metrics_max_drawdown_r` — max drawdown from champion metrics
- `calmar` — computed as `metrics_return / abs(metrics_max_drawdown_r)` in Cypher
- `is_oos_drift` — `true` when `abs(metrics_oos_sharpe - metrics_sharpe) / abs(metrics_sharpe) > 0.20`

CSV pre-condition (discovered at implementation time):
Current artifact CSVs are parameter-sweep results. They do NOT contain `daily_pnl` or
`equity` columns. Champions backed by such CSVs are skipped with a warning per AC3.

---

## Shell Hook Integration Contract

Execution entrypoints remain unchanged:
- `research/bin/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/bin/run_es_phase2.sh`

Hook rule:
- Add post-run ingestion with soft fail.

Contract example:
```zsh
qw record --file "results/es_bear_baseline.csv" --kind baseline_csv || true
qw record --file "results/nq_bear_baseline.csv" --kind baseline_csv || true
```

Guarantees:
- Existing script flags and behavior are unchanged.
- Graph ingestion failure must not abort research run.
- Failure details must be emitted to STDERR.

Pivot linkage (champion ingest):
```zsh
qw record --file "research/results/champions/es_bear_sweep_1h_v1.md" \
  --kind champion_md \
  --pivot-from "a1b2c3d4e5f6" || true
```

---

## CLI Spec (Man-page style)

### `qw record`
Purpose:
- Parse an artifact, validate schema, persist to graph or pending queue.

Online default behavior:
- If Neo4j is reachable, write directly to graph.
- If Neo4j is unreachable and `--offline` is not set, return infra failure.

Usage:
```text
qw record --file <path> --kind <baseline_csv|grid_csv|champion_md|tracker_md> [options]
```

Options:
- `--file <path>`: artifact path (required)
- `--kind <kind>`: artifact kind (required)
- `--pivot-from <run_id>`: explicit pivot link for champion ingestion
- `--oos <status>`: OOS validation outcome (oos_pass | oos_fail | oos_pending), requires --champion
- `--champion <id>`: Champion node ID (required with --oos)
- `--sharpe <float>`: OOS Sharpe ratio to store on Champion (optional with --oos; must be non-negative)
- `--offline`: skip Neo4j write; write pending payload
- `--timeout-seconds <int>`: Neo4j timeout (default 3)
- `--repo-root <path>`: optional repo root override
- `--dry-run`: parse + validate + preview, no write

Exit codes:
- `0`: success
- `1`: validation error
- `2`: infra error

### `qw reconcile`
Purpose:
- Compare expected ingested artifacts against graph records.

Usage:
```text
qw reconcile [--since <ISO8601>] [--json]
```

Output:
- missing in graph
- missing in artifacts
- hash/provenance mismatch

Commit guidance:
- Implement in the same story/PR as `qw record`, but in a separate commit for review clarity.

### `qw query`
Purpose:
- Run predefined graph queries for research retrieval.

Usage:
```text
qw query --name <query_name> [--param key=value ...]
```

V1 query examples:
- `recent_champions`
- `strategy_lineage`
- `pending_offline`

---

## Offline Sync Protocol

### Pending write format
- `.qws/pending/<id>.json` stores validated `ResearchArtifact` payload + metadata.

### Sync command behavior (`qw sync`)
1. Read pending files oldest-first.
2. Validate payload schema again.
3. Persist transaction to Neo4j.
4. On success:
   - write receipt in `.qws/receipts/`
   - remove pending file
5. On failure:
   - leave pending file untouched
   - emit STDERR summary

### Idempotency requirement
- Running `qw sync` repeatedly must not produce duplicates.

---

## Testing and Validation Expectations

### Fixture locations
- `tests/fixtures/artifacts/baseline/*.csv`
- `tests/fixtures/artifacts/grid/*.csv`
- `tests/fixtures/artifacts/champion/*.md`
- `tests/fixtures/artifacts/tracker/*.md`

### Required tests
- Parser success/failure tests per artifact type.
- Unknown field tolerance test (`extra='ignore'`).
- Required field missing test (must fail).
- Idempotent ingest test (double-ingest no new nodes).
- Round-trip hash test (artifact -> model -> export -> hash unchanged).
- Offline mode tests (`--offline`, `--dry-run`).

### Performance/continuity test
- Run a 100-iteration sweep with Neo4j down and hook enabled with `|| true`.
- Verify research script completes.

---

## Non-Goals / Deferred Scope

Deferred beyond V1:
- MCP write path.
- VS Code HUD/CodeLens features.
- Live-instance monitoring/drift graph.
- Rich structured parsing of `research/es_nq_bear_sweep_tracker.md`.
- Cloud/tunnel deployment.

---

## Locked Epic 1 Infra Defaults

These defaults are locked for Epic 1 / Story 0 unless they conflict with hard runtime constraints.

- Neo4j image: 5.x Community Edition.
- Compose service name: `qws-neo4j`.
- Ports:
  - `7474:7474` (HTTP)
  - `7687:7687` (Bolt)
- Dev auth default: `neo4j/password` (overridable via `.env`).
- Persistent volume path: `./.qws/neo4j_data`.
- Python CLI entrypoint: `qw` -> `research.graph.cli:main` (configured in `pyproject.toml`).

---

## Open Quantitative Unknowns

### Benchmark basket
Open item requiring quant approval after ledger population:
- exact market-independence benchmark basket composition and weights
  (ES/NQ/RTY weighting policy is not final in V1).

---

## Implementation Ready Now

Unblocked tasks:
- Pydantic models in `research/graph/models.py`.
- Parsers in `research/graph/parsers.py`.
- `qw record` CLI scaffold in `research/graph/cli.py`.
- Receipt + pending directory handling under `.qws/`.
- Neo4j store layer in `research/graph/store.py` with MERGE semantics.
- Shell hook integration patches for:
  - `research/bin/run_es_nq_bear_sweep_1h_baseline.sh`
  - `research/bin/run_es_phase2.sh`
- Reconcile/query command shells.

## Implementation Checklist (Story 1 Contract Gates)

- [x] Artifact kind enum is explicit and consistent across schema, CLI kind values, pending payloads, and receipts.
- [x] Deterministic ID algorithm is fixed (`normalize_text` + SHA-256 `hash12`) with explicit collision fail-fast policy.
- [x] `qw record` exit codes are exact and exhaustive for V1 (`0`, `1`, `2`, plus dry-run write behavior).
- [x] `.qws/receipts` and `.qws/pending` write conditions are explicitly defined.
- [x] Cypher MERGE mappings are specified for CSV ingest and champion ingest.

---

## Future Decision Hooks

Intentionally deferred:
- Final benchmark basket weighting.
- Visualizer choice beyond Neo4j Browser.
- MCP write-path design.
- HUD/CodeLens productization.


