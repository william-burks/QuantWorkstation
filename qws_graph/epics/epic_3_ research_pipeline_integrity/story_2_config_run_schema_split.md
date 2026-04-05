# Story 2 — Config/Run Schema Split: Domain-Specific Metadata Expansion

## ID
# QWS-0302

## Status
draft

## Priority
P2 — Correctness. The ingestion pipeline currently drops any CSV column not in the
core schema with an `Unknown columns: <name>` warning and silent discard. Trial parameters
like `sizing_mode`, `wick_mode`, and `target_r` are configuration choices that determine
run behaviour — losing them at ingestion time makes it impossible to query the graph by
how a strategy was configured, not just how it performed.

## Why
When a trial introduces a new parameter column (e.g. `sizing_mode`), the ingestion layer
has no slot for it and drops it silently. This is the Schema Evolution problem: the pipeline
is rigid and correct for the core schema, but any experiment that adds a domain-specific
parameter produces a warning and a data loss.

The root cause is a missing separation of concerns in the schema:

- **Parameters** — configuration choices made before the run (`sizing_mode`, `wick_mode`,
  `target_r`, `instrument`, `time_stop`). These belong on the `:Config` node. They answer
  *"how was this run configured?"*
- **Results** — outcomes measured after the run (`sharpe`, `calmar`, `win_rate`,
  `max_drawdown`, `profit_factor`). These belong on the `:Run` node. They answer
  *"how did this run perform?"*

Conflating both on `:Run` (or dropping parameters entirely) prevents the graph from
answering cross-sectional questions like:
> "Show me the average Sharpe for all runs using `vol_target` sizing vs `fixed` sizing."

That query requires `sizing_mode` to live as a property on `:Config`, not buried in a
metrics blob on `:Run`.

## Approach Decision: Typed Schema over Flex-Field

Two options were considered:

**Path A — Flex-Field:** stuff unknown columns into a single `extra_metadata` JSON string
on `:Run`. Zero schema changes, but `sizing_mode` is not queryable without JSON extraction.
Ruled out: defeats the purpose of a graph store for research analysis.

**Path B — Typed Schema (chosen):** declare domain-specific parameters as first-class
properties on `:Config`. The `GraphStore` inspects CSV headers against a schema registry
to route each column to the right node type at ingestion time.

Path B is the correct choice for a research workbench. Every new parameter that becomes
queryable is worth a one-time schema declaration. The overhead is a single line in a
registry, not a code change per parameter.

## Summary
Define a schema registry that separates trial CSV columns into two buckets — Config
parameters and Run results — and update the ingestion layer to route each column to the
correct node at write time. Columns not in either bucket raise a structured warning (not a
silent discard) and are excluded from ingestion until registered.

## Goal
- `sizing_mode`, `wick_mode`, `target_r`, and any other trial-specific parameters land on
  the `:Config` node as typed properties.
- Core result metrics (`sharpe`, `calmar`, `win_rate`, etc.) remain on `:Run`.
- The Cypher `CSV_INGEST_QUERY` is updated to SET Config properties from the registry.
- Unknown columns produce a structured warning that names the column and the story/registry
  file to update — not a silent drop.
- A Cypher query like `MATCH (c:Config) WHERE c.sizing_mode = 'vol_target' RETURN c`
  returns results.

## Proposed Design

### Schema Registry
Define a central registry (e.g. `qws_graph/research/graph/schema_registry.py`) that maps
column names to their destination node and type:

```python
# Columns that belong on :Config (parameters — set before the run)
CONFIG_PROPERTIES: set[str] = {
    "sizing_mode",
    "wick_mode",
    "target_r",
    "instrument",
    "time_stop",
    "strategy_id",   # already on Config — confirm placement
}

# Columns that belong on :Run (results — measured after the run)
RUN_PROPERTIES: set[str] = {
    "sharpe",
    "calmar",
    "win_rate",
    "max_drawdown",
    "profit_factor",
    "total_trades",
    "avg_return",
    "run_id",        # already on Run — confirm placement
}
```

### GraphStore Routing Logic
In `_persist_csv`, split the CSV row into two payload dicts before building the Cypher
query — one for `:Config` properties and one for `:Run` properties:

```python
config_payload = {k: v for k, v in row.items() if k in CONFIG_PROPERTIES}
run_payload    = {k: v for k, v in row.items() if k in RUN_PROPERTIES}
unknown        = set(row.keys()) - CONFIG_PROPERTIES - RUN_PROPERTIES - IGNORED_COLUMNS

if unknown:
    logger.warning(
        "Unknown columns during ingestion — add to schema_registry.py: %s", unknown
    )
```

### Cypher Update
Extend `CSV_INGEST_QUERY` to SET Config properties from `config_payload`:

```cypher
MERGE (c:Config {config_id: $config_id})
SET c += $config_payload
```

## In Scope
- `schema_registry.py` — new file defining `CONFIG_PROPERTIES`, `RUN_PROPERTIES`,
  `IGNORED_COLUMNS`.
- `store.py` `_persist_csv` — routing logic and structured unknown-column warning.
- `cypher.py` `CSV_INGEST_QUERY` — SET Config properties from `config_payload`.
- Unit tests covering: known config column routes to Config payload, known run column routes
  to Run payload, unknown column triggers warning and is excluded.

## Out of Scope
- Back-filling existing `:Config` nodes with `sizing_mode` values (separate migration).
- Auto-discovery or inference of column types from data values.
- Any changes to the `:Champion` or `:Strategy` node schemas.

## Repo Touchpoints
- `qws_graph/research/graph/schema_registry.py` — new
- `qws_graph/research/graph/store.py` — `_persist_csv` routing logic
- `qws_graph/research/graph/cypher.py` — `CSV_INGEST_QUERY` Config SET clause
- `tests/unit/` — schema routing unit tests

## Acceptance Criteria
- [ ] A trial CSV with a `sizing_mode` column ingests without `Unknown columns` warning.
- [ ] `MATCH (c:Config) WHERE c.sizing_mode = 'vol_target' RETURN c` returns results after
  ingestion of a run that used `vol_target` sizing.
- [ ] A CSV column not in `CONFIG_PROPERTIES` or `RUN_PROPERTIES` produces a logger warning
  that names the column — it is not silently dropped.
- [ ] Existing core metrics (`sharpe`, `calmar`, `win_rate`) still land on `:Run` nodes
  without regression.
- [ ] Unit tests pass for the routing logic.

## Dependencies
- Story 1 (QWS-0301) — schema consistency baseline must be stable before extending the
  schema. Do not start this story if `curator_note` normalization is not complete.
- Story 3 (QWS-0303) — the centralized ingestion layer will own `schema_registry.py` once
  built; coordinate to avoid conflicts if both stories run concurrently.

## Open Questions
- Which columns are currently implicit `:Config` properties vs `:Run` properties? Audit
  `cypher.py` `CSV_INGEST_QUERY` SET clauses before finalising the registry.
- Should `strategy_id` and `run_id` be in the registry or treated as join keys outside it?
- Is `IGNORED_COLUMNS` needed for housekeeping columns (e.g. `timestamp`, `source_file`)
  that are neither Config nor Run properties?
