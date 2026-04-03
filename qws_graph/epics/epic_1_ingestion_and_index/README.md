# Epic 1 — Ingestion and Index

## Objective
Stand up Graph V1 sidecar ingestion without changing existing research execution entrypoints.

## Why it exists
The repository already produces baseline/grid CSVs and champion markdowns, but lineage and cross-run relationships are not queryable as a ledger.

## Scope
- Add infra scaffold for local Neo4j and graph settings
- Implement fixed ingestion contract from `docs/graph_v1_contract.md`
- Parse and validate artifact payloads
- Add `qw record` and idempotent Neo4j writes
- Add soft-fail shell hooks and reconciliation support

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

## Exit criteria
- `qw record` ingests baseline/grid/champion artifacts with deterministic IDs
- Re-ingest does not duplicate graph state
- Shell hooks run with `|| true` and do not break existing runs
- Reconcile command can report pending/drift state

