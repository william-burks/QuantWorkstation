# Story 0 — Target State Schema Mapping

## Status
draft

## Summary
Lock the Epic 2 read/query topology before Story 1 so read models and presets map to a stable graph shape.

## Problem
Without an explicit node/relationship map, Story 1 read models and Story 2 query presets can drift from Graph V1 contracts.

## Goal
Define a repo-native schema mapping contract for Epic 2 read paths using Graph V1 canonical labels and relationship types.

## Inputs
- `qws_graph/docs/graph_v1_contract.md`
- Epic 1 ingestion/store implementation

## Deliverable
- This mapping contract document as the Story 0 gate for Story 1+

## Node Labels (Canonical in Graph V1)
- `Strategy`
  - Key: `strategy_id`
  - Core properties: `instrument`, `timeframe`, `direction`, `logic_type`
- `Run`
  - Key: `run_id`
  - Core properties: `timestamp`, metrics fields, `artifact_path`, provenance fields
- `Config`
  - Key: `config_id`
  - Core properties: `params_json`, `risk_params`
- `Champion`
  - Key: `champion_id`
  - Core properties: `strategy_id`, `freeze_date`, summary/OOS fields, provenance fields
- `BlobArtifact`
  - Key: `artifact_path`
  - Core properties: `artifact_kind`, hash/provenance metadata

## Relationship Types (Canonical in Graph V1)
- `(:Strategy)-[:HAS_RUN]->(:Run)`
- `(:Run)-[:USES_CONFIG]->(:Config)`
- `(:Strategy)-[:PRODUCED_CHAMPION]->(:Champion)`
- `(:Champion)-[:PIVOTED_FROM]->(:Run)`
- `(:Strategy)-[:HAS_BLOB]->(:BlobArtifact)`

## Requested Connection Mapping (User Terms -> V1 Canonical)
1. `(:Strategy)-[:HAS_RUN]->(:ResearchRun)`
   - Canonical V1: `(:Strategy)-[:HAS_RUN]->(:Run)`
   - Read alias allowed in docs/DTO naming: `ResearchRun` -> `Run`

2. `(:ResearchRun)-[:PRODUCED]->(:Artifact)`
   - Canonical V1 representation:
     - Run CSV provenance is stored on `Run` properties (`artifact_path`, hash/provenance)
     - Champion docs are first-class `Champion` nodes via `(:Strategy)-[:PRODUCED_CHAMPION]->(:Champion)`
     - Tracker/raw docs use `(:Strategy)-[:HAS_BLOB]->(:BlobArtifact)`
   - Epic 2 rule: do not add a new persisted generic `:Artifact` node in V1

3. `(:Artifact)-[:PIVOTED_FROM]->(:Artifact)`
   - Canonical V1: `(:Champion)-[:PIVOTED_FROM]->(:Run)`
   - Read alias semantics for lineage may present this as artifact-to-artifact lineage, but storage remains Champion-to-Run

4. `(:ResearchRun)-[:TARGETS]->(:Instrument {ticker: 'ES'})`
   - Canonical V1: instrument is a property on `Strategy` (`Strategy.instrument`)
   - Query pattern for run targeting in V1: `(:Strategy {instrument: ...})-[:HAS_RUN]->(:Run)`
   - Epic 2 rule: no new `:Instrument` node/edge introduced in this epic

## Query Design Implications for Epic 2
- Story 1: read DTOs map from canonical nodes/edges above; alias naming can exist at DTO layer only.
- Story 2: presets encode canonical Cypher patterns; no ad-hoc/free-form Cypher surface.
- Story 3: MCP adapter exposes Story 1/2 outputs and should not bypass this mapping.
- Story 4: acid-test scenarios must prove lineage and cross-instrument/timeframe retrieval using canonical anchors.

## Implementation Guardrails (Normative)
- Projection shape: outputs are flattened, deterministic JSON dictionaries (lists of flat objects allowed for lineage/history collections).
- Query execution boundary: view functions are code-defined in `research/graph/query.py`; callers bind by name and do not embed duplicate query logic.
- Read source of truth: Neo4j is the only read source for Epic 2 query paths; no file fallback to CSV/Markdown artifacts.

## Acceptance Criteria
- [ ] Node labels and relationship types for Epic 2 reads are explicit and version-aligned with Graph V1.
- [ ] All Story 1/2/3/4 query surfaces reference canonical graph semantics (aliases documented where used).
- [ ] No write-model changes or new persisted node labels are introduced by Epic 2 Story 0.

## Notes
If future requirements require `ResearchProject`, `ResearchRun`, `Artifact`, or `Instrument` as persisted labels, that is a contract revision (Graph V2+), not an Epic 2 read-layer change.

