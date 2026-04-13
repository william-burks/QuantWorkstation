# Baseline Protocol

The canonical clean baseline command for QuantWorkstation is:

```
make test-all
```

This runs both test suites in sequence:
- `qws_graph/tests/unit/` — graph module unit tests
- `tests/unit/` — data/execution/strategy unit tests

## Rules

- All agents use `make test-all` for baseline and regression checks.
- Pre-existing failures are **recorded, not debugged**. Record them and continue.
- Never retry the same command more than once.
- A failure that appears in the current run but NOT in the baseline = regression. Investigate.
- A failure present in both baseline and current = pre-existing. Skip.

## Per-agent usage

| Agent | Command | Step |
|-------|---------|------|
| qa-epic | `make test-all 2>&1 \| tee /tmp/qa_epic_$EPIC_baseline.txt` | Step 0 (baseline) |
| qa-epic | `make test-all 2>&1 \| tee /tmp/qa_epic_$EPIC_current.txt` | Step 2f (regression diff) |
| run-epic | `make test-all` | Step 3 (pre-flight) |
| verify-story | `make test-all 2>&1` | Step 2 |
| implement-story | `make test` | Step 4 (per-change check — qws_graph suite only, sufficient during impl) |

## Neo4j dependency

Integration tests (`make test-integration`) require Neo4j. If unreachable, note "skipped" and continue. Never block on Neo4j availability.
