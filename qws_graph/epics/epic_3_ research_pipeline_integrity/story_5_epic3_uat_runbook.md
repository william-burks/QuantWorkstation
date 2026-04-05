# Story 5 — Epic 3 UAT Runbook

## ID
# QWS-0305

## Status
draft

## Summary
Documentation-only story. Define a UAT runbook that lets the operator verify all three
Epic 3 stories are correctly implemented by executing a single end-to-end test sequence
from a clean Neo4j state. The runbook is the deliverable — this story is done when the
runbook exists and all checklist items pass.

## Inputs
- Story 1 — Graph Ingestion Schema Consistency (env sourcing, `curator_note`, champion promotion)
- Story 2 — Centralized Ingestion Layer (`research/graph_export.py`, no hardcoded metadata in trial scripts)
- Story 3 — Trial Bundle Structure (per-run `runs/{timestamp}/` layout, `qw record --bundle`)
- `qws_graph/docs/qws_graph_runbook.md` (existing operator runbook — update with Epic 3 additions)
- `qws_graph/env.example` (canonical env var reference)

## Deliverable
An appendix section added to `qws_graph/docs/qws_graph_runbook.md`:
**"Epic 3 — Research Pipeline Integrity: UAT Verification"**

---

## UAT Runbook

### Prerequisites
- Neo4j is running (`make neo4j-up && make neo4j-status`).
- Python environment is active with all dependencies installed (`pip install -e ".[dev]"`).
- `qws_graph/.env` is present and correct (see `qws_graph/env.example`).
- `qw record --help` exits `0`.

---

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

### Phase 1 — Environment Sourcing (Story 1, Part B)

Verify the shell runner sources `qws_graph/.env` without pre-exported graph vars.
Open a clean subshell with no graph vars set:

```zsh
env -i HOME=$HOME PATH=$PATH SHELL=$SHELL zsh
cd /Users/will/ClaudeProjects/QuantWorkstation
source .venv/bin/activate
./research/run_liquidity_sweep_baseline.sh
```

Expected:
- Script completes without `Neo4j connectivity check failed` or similar error.
- Receipt exists in `.qws/receipts/` with `status: persisted`.
- Exit `0`.

If connectivity fails, verify `qws_graph/.env` has correct `QW_GRAPH_HOST` and
`QW_GRAPH_PASSWORD` values matching the running Neo4j instance.

---

### Phase 2 — Schema Audit (Story 1, Parts A and B)

Verify node labels and `curator_note` property key:

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

### Phase 3 — Centralized Ingestion Layer (Story 2)

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

### Phase 4 — Trial Bundle Structure (Story 3)

Run the baseline again and confirm bundle output:

```zsh
./research/run_liquidity_sweep_baseline.sh
```

Expected directory structure:
```
research/trials/futures/liquidity_sweep/runs/
  <YYYYMMDD-HHMMSS>/
    baseline_results.csv
    report.html
    bundle.json
```

Inspect the manifest:
```zsh
cat research/trials/futures/liquidity_sweep/runs/*/bundle.json | python -m json.tool
# Expected: "files" key with "csv" and "html" entries
```

Ingest via bundle:
```zsh
BUNDLE_DIR=$(ls -dt research/trials/futures/liquidity_sweep/runs/*/ | head -1)
qw record --bundle "$BUNDLE_DIR"
```

Expected:
- Exit `0`.
- Receipt written with `status: persisted`.
- Receipt includes the `run_id` generated post-parse.

Verify HTML blob linked in graph:
```cypher
MATCH (s:Strategy)-[:HAS_BLOB]->(b:BlobArtifact)
RETURN s.strategy_id, b.artifact_path, b.artifact_kind;
// Expected: at least one row with artifact_kind = "report_html"
```

---

### Phase 5 — Golden Run and Champion Promotion (Story 1, Part C)

Run the golden strategy:
```zsh
./research/run_liquidity_sweep_golden.sh
```

Verify Champion node was created:
```cypher
MATCH (ch:Champion) RETURN ch.champion_id, ch.oos_status, ch.freeze_date;
// Expected: at least one Champion node
```

Verify `qw query` surfaces it:
```zsh
qw query --name recent_champions --json
# Expected: non-empty result list containing the golden run champion
```

Verify end-to-end graph shape:
```cypher
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
RETURN s.strategy_id, ch.champion_id, ch.oos_status;
// Expected: at least one Strategy → Champion link
```

---

### Phase 6 — Regression Check

Re-run `run_liquidity_sweep_baseline.sh` a second time (idempotency):
```zsh
./research/run_liquidity_sweep_baseline.sh
```

```cypher
// Node counts must not double
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;
// Expected: same counts as after Phase 2 (MERGE semantics — no duplicates)
```

---

### Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `Neo4j connectivity check failed` on env-clean run | `.env` not sourced by shell runner | Story 1 Part B not implemented — verify `.env` source block in script |
| `MATCH (r:Run) WHERE r.curator_note IS NULL` returns non-zero | `curator_note` still set to null | Story 1 Part A not implemented — check `store.py` `_persist_csv` |
| `grep` finds `instrument.*"CL"` in trial scripts | Script not migrated to `graph_export.py` | Story 2 not implemented for that trial |
| `runs/<timestamp>/` directory not created | Trial script not parameterized for bundle output | Story 3 not implemented |
| `qw record --bundle` fails with "no bundle.json" | `bundle.json` not written by trial | Story 3 manifest generation not implemented |
| `qw query --name recent_champions` returns empty | Champion not promoted after golden run | Story 1 Part C not implemented |
| Node counts double on re-run | MERGE semantics broken | Do not fix here — regression in Epic 1 foundations |

---

## In Scope
- Appendix section in `qws_graph/docs/qws_graph_runbook.md`.
- No implementation changes — this story is pure documentation and verification.

## Out of Scope
- New CLI flags or schema changes (those belong to Stories 1-3).
- Automated test scripts (the runbook steps are manual UAT by design).

## Repo Touchpoints
- `qws_graph/docs/qws_graph_runbook.md` — new "Epic 3 UAT" appendix section

## Acceptance Criteria
- [ ] All six UAT phases complete without failures from a clean Neo4j state.
- [ ] `qw query --name recent_champions` returns the golden champion after Phase 5.
- [ ] `MATCH (r:Run) WHERE r.curator_note IS NULL RETURN count(r)` returns `0`.
- [ ] No hardcoded `instrument = "CL"` in any `research/trials/` file.
- [ ] Bundle directory structure (`runs/<timestamp>/`) exists after baseline run.
- [ ] Epic 3 UAT appendix added to `qws_graph/docs/qws_graph_runbook.md`.

## Definition of Done
- [ ] All six phases pass.
- [ ] Runbook appendix written.
- [ ] Story marked CLOSED.

## Dependencies
- Depends on Stories 1, 2, and 3 all being implemented. Do not begin UAT until all three
  are done — partial implementation will produce misleading failures.
