# Story 5 Runbook Notes

## Hook behavior

Both shell entrypoints now call `qw record` using a soft-fail pattern:

- `research/run_es_nq_baseline.sh`
- `research/run_es_phase2.sh`

Hook rules implemented:

1. If expected artifact file does not exist, emit warning and continue.
2. If `QW_GRAPH_ENABLED=false`, run `qw record ... --offline || true`.
3. Otherwise run `qw record ... || true`.
4. Hook failures never stop research script execution.

## Verification notes (current state)

Observed during Story 5 validation:

- Hooks run in both scripts and do not stop execution.
- Scripts currently do not create the expected `results/*.csv` artifacts in these single-run paths.
- When artifact files are missing, hooks now emit a warning and continue.

This means receipt/pending creation in script paths is blocked until those script paths emit files consistently.

## Operator quick checks

### Online mode (receipt path)

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true zsh research/run_es_nq_baseline.sh
ls -la .qws/receipts
```

Expected: receipt JSON files are written under `.qws/receipts/` for any artifact files present at hook paths.

### Offline mode (pending path)

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=false zsh research/run_es_phase2.sh 1a
ls -la .qws/pending
```

Expected: pending payload JSON files are written under `.qws/pending/` for any artifact files present at hook paths.

### Warning/retry visibility

```zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
QW_GRAPH_ENABLED=true QW_GRAPH_PORT=1 zsh research/run_es_phase2.sh 1a
```

Expected: `qw record` warning/retry messaging appears on STDERR, and the script still completes.


