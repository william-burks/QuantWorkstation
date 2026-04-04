# Story 5 Runbook Notes

## Hook behavior

Both shell entrypoints now call `qw record` using a soft-fail pattern:

- `research/run_es_nq_bear_sweep_1h_baseline.sh`
- `research/run_es_phase2.sh`

Hook rules implemented:

1. Add `sleep 1` after Python script exit to allow filesystem sync before artifact check.
2. If expected artifact file does not exist, emit warning and continue.
3. If `QW_GRAPH_ENABLED=false`, run `qw record ... --offline || true`.
4. Otherwise run `qw record ... || true`.
5. Hook failures never stop research script execution.

## Artifact filename convention

Artifact filenames must encode strategy metadata for the parser to infer
`instrument`, `timeframe`, `direction`, and `logic_type`. The pattern is:

```
{instrument}_{direction}_{logic}_{timeframe}_{descriptor}.csv
```

Examples:
- `results/es_bear_sweep_1h_baseline.csv`   ← ES baseline
- `results/nq_bear_sweep_1h_baseline.csv`   ← NQ baseline
- `results/es_bear_sweep_1h_nypre.csv`      ← ES phase 2, NY_PRE only
- `results/es_bear_sweep_1h_grid_nypre_v1.csv`  ← ES grid search

Names that omit the timeframe token (e.g., `es_bear_baseline.csv`) cause
`qw record` to fail with `could not resolve strategy fields: timeframe`.

## Verification notes

End-to-end offline path verified 2026-04-04:

```
$ qw record --file results/es_bear_sweep_1h_baseline.csv --kind baseline_csv --offline
OK: baseline_csv persisted to pending queue (.qws/pending/4146b8e552b6.json)
```

Receipt written to `.qws/receipts/4146b8e552b6.json` with `status: pending_offline`.
Pending payload written to `.qws/pending/4146b8e552b6.json`.

## Operator quick checks

### Online mode (receipt path)

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
# Requires Neo4j running (docker compose -f docker-compose.neo4j.yml up -d)
QW_GRAPH_ENABLED=true zsh research/run_es_nq_bear_sweep_1h_baseline.sh
ls -la .qws/receipts
# Expected: receipt JSON with status=persisted for each artifact
```

### Offline mode (pending path)

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/run_es_phase2.sh 1a
ls -la .qws/pending
# Expected: pending JSON with status=pending_offline
# Expected: receipt JSON with status=pending_offline
```

### Warning/retry visibility (Neo4j down)

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true QW_GRAPH_PORT=1 zsh research/run_es_phase2.sh 1a
# Expected on STDERR: WARNING Neo4j unavailable (timeout after 3s)
# Expected on STDERR: INFO: Start Neo4j or rerun with --offline
# Expected: script still completes (exit 0 due to || true)
```

### Reconcile pending queue

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
qw reconcile
# Human format

qw reconcile --json
# JSON format
```
