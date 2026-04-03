# Epic 1 — Ingestion and Index

## Objective
Stand up Graph V1 sidecar ingestion without changing existing research execution entrypoints.

## Why it exists
The repository already produces baseline/grid CSVs and champion markdowns, but lineage and cross-run relationships are not queryable as a ledger.

## Scope
- Add infra scaffold for local Neo4j and graph settings
- Implement fixed ingestion contract from `docs/graph_v1_contract.md`
- Parse and validate artifact payloads
- Add `qw record` + `qw reconcile` and idempotent Neo4j writes
- Add soft-fail shell hooks and receipt/pending operations

## Stories in execution order
1. `story_0_infra_scaffold_and_docker.md`
2. `story_1_graph_v1_contract_alignment.md`
3. `story_2_pydantic_models_and_parsers.md`
4. `story_3_qw_record_cli.md`
5. `story_4_neo4j_idempotent_store.md`
6. `story_5_shell_hooks_receipts_and_reconcile.md`

## Dependencies
- Existing artifact outputs under `results/` and `research/results/champions/`
- Existing scripts: `research/run_es_nq_baseline.sh`, `research/run_es_phase2.sh`
- Existing validation conventions in `research/candidate_validator.py`, `data/schemas/`

## Story 0 quickstart (local Neo4j)
- Copy `env.example` to `.env` and adjust values if needed.
- Start Neo4j with `make neo4j-up`.
- Check status with `make neo4j-status`.
- View logs with `make neo4j-logs`.
- Neo4j Browser is available at `http://localhost:7474`.
- Set `QW_GRAPH_ENABLED=false` when you want graph-disabled mode with no Neo4j dependency.
- Stop Neo4j with `make neo4j-down`.

## Exit criteria
- `qw record` ingests baseline/grid/champion artifacts with deterministic IDs
- `qw reconcile` can audit pending/drift state from CLI
- Re-ingest does not duplicate graph state
- Shell hooks run with `|| true` and do not break existing runs
- Receipt and pending behavior is verified through shell entrypoints
