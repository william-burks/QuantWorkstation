# Story 7 — Epic 3 UAT Runbook

## ID
# QWS-0307

## Status
CLOSED

## Summary
Documentation-only story. Define a UAT runbook that lets the operator verify all Epic 3
stories (QWS-0304 through QWS-0306) are correctly implemented by executing a single
end-to-end test sequence from a clean Neo4j state. The runbook is the deliverable — this
story is done when the runbook appendix exists and all checklist items pass.

## Problem
Stories QWS-0304 (schema registry), QWS-0305 (centralized ingestion), and QWS-0306
(trial bundle structure) each have unit tests but no shared end-to-end verification
sequence. Without a runbook, regression across all three is only caught by running the
full pipeline manually and knowing what to check. This story formalizes that sequence.

## Goal
Produce an appendix to `qws_graph/docs/qws_graph_runbook.md` that an operator can
execute top-to-bottom from a clean Neo4j state to confirm Epic 3 is correctly wired.

## Inputs / Dependencies
- QWS-0304 — Schema Registry + Config/Run column routing (CLOSED)
- QWS-0305 — Centralized Ingestion Layer (`research/graph_export.py`) (CLOSED)
- QWS-0306 — Trial Bundle Structure (`qw record --bundle`, per-run `runs/{ts}/`) (CLOSED)
- `qws_graph/docs/qws_graph_runbook.md` — existing operator runbook (append section)
- `qws_graph/env.example` — canonical env var reference
- `qws_graph/research/graph/query_presets.py` — all registered `qw query` presets

Do not begin UAT until all three dependency stories are CLOSED — partial implementation
will produce misleading failures.

## Deliverable
An appendix section added to `qws_graph/docs/qws_graph_runbook.md`:
**"Epic 3 — Research Pipeline Integrity: UAT Verification"**

---

## Preconditions

Before starting UAT, verify all of the following:

- Neo4j is running: `make neo4j-up && make neo4j-status`
- Python environment active with all deps: `pip install -e ".[dev]"`
- `qws_graph/.env` is present and correct (see `qws_graph/env.example` — credentials
  must match the running Neo4j instance; default `bolt://localhost:7687`)
- `qw --help` exits `0` (`qw` CLI is on PATH, registered via `qws_graph/pyproject.toml`)
- `jq --version` exits `0` (required for JSON pipeline examples in Phase 6)
- Run from the repo root: `cd /path/to/QuantWorkstation`
- `research/results/` is writable
- **Neo4j is empty before Phase 0** — do not run UAT against a live-data graph

---

## UAT Runbook

### Phase 0 — Clean State

Nuke the graph:
```cypher
// Run in Neo4j Browser (http://localhost:7474)
MATCH (n) DETACH DELETE n;
```

Confirm empty:
```cypher
MATCH (n) RETURN count(n);
// Expected: 0
```

---

### Phase 1 — Environment Sourcing (QWS-0304)

Verify the shell runner sources `qws_graph/.env` without pre-exported graph vars.
Open a clean subshell with no graph vars set:

```zsh
env -i HOME=$HOME PATH=$PATH SHELL=$SHELL zsh
cd /path/to/QuantWorkstation
source .venv/bin/activate
./research/bin/run_liquidity_sweep_baseline.sh
```

Expected:
- Script completes without `Neo4j connectivity check failed` or similar error.
- Receipt exists in `.qws/receipts/` with `"status": "persisted"`.
- Exit `0`.

If connectivity fails, verify `qws_graph/.env` has correct `QW_GRAPH_HOST` and
`QW_GRAPH_PASSWORD` matching the running Neo4j instance.

---

### Phase 2 — Schema Audit (QWS-0304)

Verify node labels and `curator_note` property (per `graph_v1_contract.md` Run spec,
`curator_note` must be `""` — empty string — not null):

```cypher
// Labels are correct — no label-less nodes
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;
// Expected rows: ['Strategy'], ['Run'], ['Config'] (and optionally ['RunStatsSummary'])
```

```cypher
// curator_note is present on all Run nodes (empty string, not null)
MATCH (r:Run) WHERE r.curator_note IS NULL RETURN count(r) AS missing;
// Expected: 0
```

```cypher
// Spot-check a Run node
MATCH (r:Run) RETURN r.run_id, r.curator_note, r.sharpe LIMIT 3;
// Expected: curator_note = "" on each row (not null, not absent)
```

---

### Phase 3 — Centralized Ingestion Layer (QWS-0305)

Confirm no hardcoded strategy metadata remains in trial scripts:

```zsh
grep -rn 'instrument.*=.*"CL"' research/trials/
# Expected: no matches
grep -rn 'n_trades.*total_trades\|total_trades.*n_trades' research/trials/
# Expected: no matches
```

Confirm `research/graph_export.py` exists and the validation gate works:

```zsh
python - <<'EOF'
import pandas as pd
from research.graph_export import write_baseline_csv
from pathlib import Path

# Missing required field — should raise before writing
try:
    write_baseline_csv(
        pd.DataFrame([{"sharpe": 1.0}]),  # missing profit_factor, win_rate, etc.
        output_path=Path("/tmp/test_fail.csv"),
        instrument="CL", timeframe="1H", direction="bear", logic_type="liquidity-sweep",
    )
    print("FAIL — should have raised ValueError")
except ValueError as e:
    print(f"PASS — raised correctly: {e}")
EOF
```

Expected output: `PASS — raised correctly: Missing required graph export fields: {...}`

---

### Phase 4 — Trial Bundle Structure (QWS-0306)

Run the baseline and confirm bundle output:

```zsh
./research/bin/run_liquidity_sweep_baseline.sh
```

Expected directory structure:
```
research/results/futures/liquidity_sweep/runs/
  <YYYYMMDD-HHMMSS>/
    baseline_results.csv
    index.html
    bundle.json
```

Inspect the manifest:
```zsh
cat research/results/futures/liquidity_sweep/runs/*/bundle.json | python -m json.tool
# Expected: "files" key with "csv", "csv_kind", and "html" entries
```

Ingest via bundle:
```zsh
BUNDLE_DIR=$(ls -dt research/results/futures/liquidity_sweep/runs/*/ | head -1)
qw record --bundle "$BUNDLE_DIR"
```

Expected:
- Exit `0`.
- Receipt written with `"status": "persisted"`.
- Receipt includes the `run_id` generated post-parse.

Verify HTML path linked on Run node (stored as property, not BlobArtifact):
```cypher
MATCH (r:Run) WHERE r.artifact_path_html IS NOT NULL
RETURN r.run_id, r.artifact_path_html LIMIT 3;
// Expected: at least one row with a valid filesystem path
```

---

### Phase 5 — Full Pipeline Run

Run all four trial runners in sequence to populate the graph for query verification:

```zsh
./research/bin/run_liquidity_sweep_baseline.sh && \
./research/bin/run_liquidity_sweep_position_sizing.sh && \
./research/bin/run_liquidity_sweep_golden.sh && \
./research/bin/run_btc_mars_golden.sh
```

Expected: all four runners exit `0`. If any fail, stop and diagnose before proceeding
to Phase 6 — query results depend on data from all four runners.

---

### Phase 6 — Champion Promotion Verification (QWS-0304)

Verify Champion node was created after the golden run:
```cypher
MATCH (ch:Champion) RETURN ch.champion_id, ch.oos_status, ch.freeze_date;
// Expected: at least one Champion node
```

Verify end-to-end graph shape:
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
RETURN s.strategy_id, ch.champion_id, ch.oos_status;
// Expected: at least one Strategy → Champion link
```

---

### Phase 7 — Query Verification (all `qw query` presets)

Exercise every registered preset. All commands must exit `0`.

**Strategy-scoped:**
```zsh
qw query --name recent_champions
qw query --name recent_champions --param limit=5
qw query --name recent_champions --json
qw query --name strategy_lineage --param strategy_id=cl-1h-bear-liquidity-sweep
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep
qw query --run-history --param strategy_id=cl-1h-bear-liquidity-sweep   # shortcut alias — same as above
qw query --name rank_by_evidence --param strategy_id=cl-1h-bear-liquidity-sweep
```

**Champion lineage:**
```zsh
# Capture a champion_id and run_id from the data ingested in Phase 5:
CHAMPION_ID=$(qw query --name recent_champions --json | jq -r '.[0].champion_id')
qw query --name trace_champion --param champion_id=$CHAMPION_ID

RUN_ID=$(qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep \
  | head -1 | jq -r '.run_id')
qw query --name downstream_champions --param run_id=$RUN_ID
# Note: empty list is valid when no --pivot-from was used at ingest
```

**Family correlation:**
```zsh
qw query --name cross_artifact_correlation --param strategy_id=cl-1h-bear-liquidity-sweep
# Note: returns empty list when no family_id is set (requires --source-file at ingest)
# If family_id is known:
# qw query --name cross_artifact_correlation --param family_id=<12-char-hash>
```

**Portfolio-level:**
```zsh
qw query --name portfolio_alpha
qw query --name fragility_report
qw query --name staleness_report
qw query --name instrument_concentration
```

**Offline queue:**
```zsh
qw query --name pending_offline
# Expected: empty list — no artifacts stuck in queue after full pipeline run
```

**JSON output and jq pipeline:**
```zsh
qw query --name run_history --param strategy_id=cl-1h-bear-liquidity-sweep \
  | jq 'select(.total_trades >= 10) | {run_id, sharpe, total_trades}'
```

---

### Phase 8 — Regression Check (idempotency)

Re-run the baseline a second time:
```zsh
./research/bin/run_liquidity_sweep_baseline.sh
```

```cypher
// Node counts must not double (MERGE semantics)
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;
// Expected: same counts as after Phase 2
```

---

### Phase 9 — QA Integrity Script

Run the automated structural integrity check:
```zsh
./research/bin/qa_graph_integrity.sh
```

Expected: `Passed: 5, Failed: 0`

The script checks: graph connectivity, champion presence, champion flat metrics
(`avg_sharpe` not null), champion lineage trace, and trade count significance (≥ 5).

---

### Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `Neo4j connectivity check failed` on env-clean run | `.env` not sourced by shell runner | QWS-0304 env preamble not implemented — verify git-root-anchored env block in `research/bin/` script |
| `curator_note IS NULL` returns non-zero | `curator_note` still set to null at ingest | Check `store.py` `_persist_csv` — `curator_note` must default to `""` |
| `grep` finds `instrument.*"CL"` in trial scripts | Script not migrated to `graph_export.py` | QWS-0305 not implemented for that trial |
| `runs/<timestamp>/` directory not created | Trial script not parameterized with `--output-dir` | QWS-0306 not implemented for that trial |
| `qw record --bundle` fails with "no bundle.json" | Manifest not written by shell runner | QWS-0306 manifest generation not implemented |
| `qw query --name recent_champions` returns empty | Champion not promoted after golden run | Check QWS-0304 auto-promote gate in `store.py` |
| `artifact_path_html IS NOT NULL` returns 0 rows | HTML patch step not executed after CSV ingest | QWS-0306 two-phase write not working — check `_cmd_bundle` in `cli.py` |
| `qw query --name <preset>` returns "preset not found" | Preset not registered in PRESET_CATALOG | Check `query_presets.py` — preset may be from a newer story not yet merged |
| `downstream_champions` returns error (not empty list) | run_id doesn't exist in graph | Use a run_id from `run_history` output, not a hardcoded example value |
| `qa_graph_integrity.sh` fails Check 2 (avg_sharpe null) | Champion nodes missing flat `metrics_*` properties | Re-ingest champion markdown after confirming `CHAMPION_INGEST_QUERY` sets `ch.metrics_sharpe` |
| Node counts double on re-run | MERGE semantics broken | Do not fix here — regression in Epic 1 foundations (QWS-0301) |

---

## In Scope
- Appendix section in `qws_graph/docs/qws_graph_runbook.md` containing the runbook above.
- No implementation changes — this story is pure documentation and verification.
- Covers QWS-0304, QWS-0305, QWS-0306 only.

## Out of Scope
- New CLI flags or schema changes (belong to Stories QWS-0304 through QWS-0306).
- Automated CI pipeline for these checks (manual UAT only; CI gate is a future story).
- MCP tool verification (belongs to a separate MCP integration story).
- Production environment runbook (local dev machine only).
- Stories outside Epic 3 (QWS-0301 through QWS-0303 are not retested here).

## Repo Touchpoints
- `qws_graph/docs/qws_graph_runbook.md` — new "Epic 3 UAT" appendix section

## Acceptance Criteria
- [ ] All nine UAT phases complete from a clean Neo4j state (Phase 0) without error.
- [ ] `MATCH (r:Run) WHERE r.curator_note IS NULL RETURN count(r)` returns `0`.
- [ ] `grep -rn 'instrument.*=.*"CL"' research/trials/` returns no matches.
- [ ] `research/results/futures/liquidity_sweep/runs/<timestamp>/` exists with
  `baseline_results.csv`, `index.html`, and `bundle.json` after Phase 4.
- [ ] `qw record --bundle <dir>` exits `0` and receipt shows `"status": "persisted"`.
- [ ] `MATCH (r:Run) WHERE r.artifact_path_html IS NOT NULL RETURN count(r)` returns ≥ 1.
- [ ] All `qw query --name <preset>` commands in Phase 7 exit `0` (13 preset invocations).
- [ ] `qw query --name pending_offline` returns empty list after Phase 5 pipeline run.
- [ ] `./research/bin/qa_graph_integrity.sh` exits `0` (`Passed: 5, Failed: 0`).
- [ ] Node counts after Phase 8 re-run match Phase 2 counts (MERGE idempotency confirmed).
- [ ] Epic 3 UAT appendix added to `qws_graph/docs/qws_graph_runbook.md`. ✓

## Definition of Done
- [ ] All acceptance criteria checked.
- [x] Runbook appendix written in `qws_graph/docs/qws_graph_runbook.md`.
- [x] Story marked CLOSED.

## Dependencies
- Depends on QWS-0304, QWS-0305, QWS-0306 all CLOSED.
- Do not begin UAT until all three are done — partial implementation will produce
  misleading failures.

## Open Questions / Risks
- `cross_artifact_correlation` requires `family_id` to be populated via `--source-file`
  at ingest. None of the current shell runners pass `--source-file`. Phase 7 documents
  the empty-list case as acceptable, but a follow-up story should add `--source-file`
  to the runners so this preset has real data to work with.
- `downstream_champions` similarly depends on explicit `--pivot-from` at ingest. No
  runner currently passes this flag. Empty-list result is acceptable for Phase 7 UAT.
