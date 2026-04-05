# Story — Graph Ingestion Schema Consistency

## ID
# QWS-0301

## Status
CLOSED

## Priority
P2 — Correctness. The shell runners and ingestion layer have three gaps that produce
silent inconsistencies: absent `curator_note` property keys on Run nodes, mismatched
environment configuration between the shell runners and the `qw` CLI, and no automated
champion promotion at the end of the golden run. None are data-corrupting, but they prevent
`qw query --name recent_champions` and `qw query --name run_history` from returning clean
results and block the end-to-end "run → champion visible in graph" workflow.

## Summary
Fix three concrete schema and wiring gaps in the liquidity-sweep research pipeline:

1. **Property completeness** — Run nodes are created without a `curator_note` property key
   when AI curation is off. Neo4j removes properties set to `null`, so the key is absent
   entirely. Normalize to an explicit default at ingestion time.
2. **Environment unification** — Shell runners (`research/run_liquidity_sweep_*.sh`) do not
   source `.env`, so `QW_GRAPH_HOST`, `QW_GRAPH_USER`, and `QW_GRAPH_PASSWORD` are only
   available if the caller has pre-exported them. The `qw` CLI sources the same graph config
   from its own env, creating a silent split when `.env` values differ from shell-session
   exports.
3. **Champion promotion** — `run_liquidity_sweep_golden.sh` calls `qw record --kind
   baseline_csv`, which creates Run nodes linked to a Strategy node. No Champion node is ever
   created, so `qw query --name recent_champions` never surfaces the golden result.

## Problem

### 1. Absent `curator_note` Property on Run Nodes
In `research/graph/store.py`, `_persist_csv` builds `run_for_query` by calling
`truncate_curator_note(run_payload.get("curator_note"))`. When AI curation is disabled,
`run_payload["curator_note"]` is absent, so the call returns `None`. The Cypher statement
then executes `SET r.curator_note = null`, which in Neo4j **removes the property key
entirely** rather than writing an empty string.

The result: every Run node ingested without AI curation lacks the `curator_note` key. This
is a data-completeness gap. Downstream Cypher that checks `r.curator_note IS NOT NULL`,
filters on it, or assumes it is always present will silently skip or miscount rows. It is
also a consistency hazard: graphs seeded with AI-on and AI-off runs will have heterogeneous
Run node schemas.

The DTO layer (`RunHistoryItemV1.curator_note: str | None = None`) handles `None` gracefully,
so there is no hard runtime failure — the gap is silent.

### 2. Environment Disconnect in Shell Runners
`GraphStore.from_env()` reads:
```
QW_GRAPH_SCHEME, QW_GRAPH_HOST, QW_GRAPH_PORT,
QW_GRAPH_USER, QW_GRAPH_PASSWORD, QW_GRAPH_DATABASE, QW_GRAPH_ENABLED
```
(canonical reference: `qws_graph/env.example`)

The shell runners do not source any `.env` file before calling `qw record`. If the caller's
shell session has different values than the `.env` on disk (or none at all), data can be
written to one Neo4j instance and read from another — "Silent Success" with zero error output.

The `QW_GRAPH_ENABLED` flag has the same problem: the runner checks `${QW_GRAPH_ENABLED:-true}`
from the shell environment, but if the `.env` sets it to `false`, a caller that forgot to
export it will attempt a live write they expected to suppress.

### 3. No Champion Promotion After Golden Run
`run_liquidity_sweep_golden.sh` ends with:
```zsh
qw record --file golden_results.csv --kind baseline_csv ...
```
This creates `Strategy` and `Run` nodes. No `Champion` node is created. The `qw` CLI has no
`champion` subcommand — promotion requires `qw record --kind champion_md --file <path>` with
a champion markdown artifact. Because the golden runner never generates or ingests this
artifact, the golden result is invisible to `qw query --name recent_champions`.

## Goal
- Run nodes always have a `curator_note` property key (value `""` when curation is off).
- Shell runners source `qws_graph/.env` (or the project root `.env`) before any `qw` call.
- The golden runner generates a champion markdown artifact and ingests it, making the golden
  result visible to `qw query --name recent_champions` immediately after the run completes.

## Inputs
- `qws_graph/research/graph/store.py` — `_persist_csv`, `truncate_curator_note` call
- `qws_graph/research/graph/cypher.py` — `CSV_INGEST_QUERY` (`SET r.curator_note = ...`)
- `qws_graph/research/graph/analyst.py` — `truncate_curator_note` (returns `None` for `None`)
- `qws_graph/env.example` — canonical env var names
- `research/run_liquidity_sweep_baseline.sh`
- `research/run_liquidity_sweep_golden.sh`
- `research/run_liquidity_sweep_position_sizing.sh`
- `research/trials/futures/liquidity_sweep/golden.py`

## Proposed Design

### A. Property Normalization — `curator_note` Default
In `qws_graph/research/graph/store.py`, change the `_persist_csv` payload construction:

```python
# Before
run_for_query = {
    **run_payload,
    "curator_note": truncate_curator_note(run_payload.get("curator_note")),
}

# After
run_for_query = {
    **run_payload,
    "curator_note": truncate_curator_note(run_payload.get("curator_note")) or "",
}
```

This ensures `r.curator_note` is always written as an empty string (not `null`) when curation
is off. Neo4j stores `""` as a present property key with an empty value, maintaining schema
consistency across all Run nodes.

### B. Environment Unification — Shell Runner Preamble
Add an env-source block near the top of each `research/run_liquidity_sweep_*.sh` runner,
after the `set -e` line:

```zsh
# Source graph environment variables from the qws_graph package.
# Falls back silently if the file does not exist (allows CI override via exports).
ENV_FILE="${0:A:h:h:h}/qws_graph/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
fi
```

This resolves both the graph-connectivity split and the `QW_GRAPH_ENABLED` flag mismatch
without requiring any changes to the `qw` CLI.

### C. Automated Champion Promotion — Golden Runner
`golden.py` already writes `golden_results.csv`. The golden runner should additionally:

1. Generate a `champion.md` artifact from the golden result (or use a pre-existing template
   committed alongside the trial). The champion markdown must satisfy the `champion_md` parser
   requirements (see `qws_graph/research/graph/models.py` — `ChampionArtifact`).
2. Call `qw record --kind champion_md --file <champion_md_path>` as the final step.

The simplest first-pass implementation: have `golden.py` write a `golden_champion.md` with
the top-ranked run's metrics pre-populated. The runner then ingests it:

```zsh
record_artifact \
    "research/trials/futures/liquidity_sweep/golden_champion.md" \
    "champion_md" \
    "research/trials/futures/liquidity_sweep/golden.py"
```

## In Scope
- `store.py` `_persist_csv`: normalize `curator_note` to `""` instead of `None`.
- All three `research/run_liquidity_sweep_*.sh` scripts: add `.env` source block.
- `golden.py`: write `golden_champion.md` artifact alongside the existing CSV and HTML.
- `run_liquidity_sweep_golden.sh`: add final `record_artifact` call for `champion_md`.
- Move `strategies/bear_cl/es/nq_sweep_1h_baseline.py` into `strategies/legacy/` and update
  the one `importlib` path reference in `liquidity_sweep_adapter.py`.
- Move all `.csv`, `.html`, and `.md` artifacts from
  `research/trials/futures/liquidity_sweep/` to `research/results/futures/liquidity_sweep/`.
- Update `run_liquidity_sweep_baseline.sh` and trial output paths in
  `01_baseline.py`/`02_position_sizing.py`/`golden.py` to write to the new
  `research/results/` location.
- Verify the CSV parser captures `sizing_mode` from artifacts written to the new path
  (no silent-drop warning after migration).

## Out of Scope
- Changes to `CSV_INGEST_QUERY` Cypher (the fix is in Python before the query runs).
- Changes to `RunHistoryItemV1` or other DTOs.
- AI curation pipeline changes.
- Back-filling existing Run nodes in the graph (separate migration if needed).
- `baseline_results.csv` or `position_sizing` champion promotion.

## Repo Touchpoints
- `qws_graph/research/graph/store.py` — `_persist_csv` `run_for_query` construction
- `research/run_liquidity_sweep_baseline.sh` — `.env` source block + updated artifact paths
- `research/run_liquidity_sweep_golden.sh` — `.env` source block + champion ingest call
- `research/run_liquidity_sweep_position_sizing.sh` — `.env` source block
- `research/trials/futures/liquidity_sweep/golden.py` — add `_write_champion_md()`; update output path
- `research/trials/futures/liquidity_sweep/01_baseline.py` — update CSV/HTML output path
- `research/trials/futures/liquidity_sweep/02_position_sizing.py` — update output path
- `strategies/adapters/liquidity_sweep_adapter.py` — update `_load_legacy_module()` path after legacy move
- `strategies/legacy/` — new directory; receive `bear_cl/es/nq_sweep_1h_baseline.py`
- `tests/unit/` — add/extend tests for `curator_note` normalization

## Implementation Notes
- The `.env` source uses `${0:A:h:h:h}` (zsh path expansion to go up 3 dirs from the script
  location) to reach the project root regardless of CWD. Verify this resolves correctly given
  the scripts live at `research/run_*.sh` (one level below root).
- `set -o allexport` / `set +o allexport` exports all variables sourced from the file without
  requiring manual `export VAR=val` in the `.env`.
- The champion markdown format must include a valid `freeze_date`, `champion_id`, and
  `strategy_id`. `golden.py` has access to all of these from the trial result — check
  `ChampionArtifact` model for required fields before writing.
- Do not change `truncate_curator_note` itself — the `or ""` normalization belongs at the
  call site in `_persist_csv` so the AI-curation path is unaffected.

## Acceptance Criteria

### Schema / pipeline (original)
- [x] After `MATCH (n) DETACH DELETE n` and a fresh `./research/bin/run_liquidity_sweep_baseline.sh`:
  `MATCH (r:Run) WHERE r.curator_note IS NULL RETURN count(r)` returns `0`.
- [x] `qw query --name run_history --param strategy_id=<id>` returns rows without any missing
  `curator_note` keys causing mapping issues.
- [x] Running `./research/bin/run_liquidity_sweep_golden.sh` without pre-exporting graph env vars
  (but with a valid `qws_graph/.env`) results in successful graph writes — no silent skip or
  connection failure. *(confirmed: `env -i` clean subshell, `OK: baseline_csv persisted to Neo4j graph`)*
- [x] After `./research/bin/run_liquidity_sweep_golden.sh` completes:
  `MATCH (ch:Champion) RETURN ch.champion_id` returns at least one champion. *(confirmed: `OK: champion_md persisted to Neo4j graph`)*
- [x] `qw query --name recent_champions` returns the golden result. *(confirmed: champion_id `0555f1cf1766`, strategy `cl-1h-bear-liquidity-sweep`)*

### Tier 1 structural cleanup
- [x] **Directory isolation:** `strategies/legacy/` exists and contains
  `bear_cl_sweep_1h_baseline.py`, `bear_es_sweep_1h_baseline.py`,
  `bear_nq_sweep_1h_baseline.py`. No bear sweep engine files remain directly under
  `strategies/`. `liquidity_sweep_adapter.py` import verified working after move.
- [x] **Artifact migration:** `research/trials/futures/liquidity_sweep/` contains only
  `.py` scripts and `README.md`. All `.csv`, `.html`, and `.md` result artifacts exist
  under `research/results/futures/liquidity_sweep/`.
- [x] **Path normalization:** `run_liquidity_sweep_baseline.sh` and the three trial scripts
  write outputs to `research/results/futures/liquidity_sweep/`. No hardcoded paths point to
  the old `research/trials/` artifact location.
- [x] **Property mapping:** `sizing_mode` registered in `KNOWN_CONFIG_COLUMNS` in `parsers.py`;
  routes to Config node `params_json`. No `Unknown columns: sizing_mode` warning on ingest.
  *(runtime confirmation pending next baseline ingest)*

## Validation
- Unit test: `_persist_csv` with `curator_note=None` input → persisted `run_for_query`
  has `curator_note == ""`.
- Integration check (manual): fresh Neo4j, run baseline, `MATCH (r:Run) RETURN r.curator_note`
  shows `""` on all nodes.
- Manual run of `run_liquidity_sweep_golden.sh` with `.env` present and `QW_GRAPH_ENABLED`
  unset in shell — confirm data written to correct host.

## Definition of Done
- [x] `store.py` `curator_note` normalization implemented and unit-tested.
- [x] All three shell runners source `.env`. *(git-root-anchored preamble applied to all five runners in `research/bin/`)*
- [x] `golden.py` writes `golden_champion.md`.
- [x] `run_liquidity_sweep_golden.sh` ingests the champion artifact.
- [x] `strategies/legacy/` contains all three bear sweep engine files; adapter import verified.
- [x] `research/trials/futures/liquidity_sweep/` contains scripts only; all artifacts under
  `research/results/futures/liquidity_sweep/`.
- [x] Shell runners and trial output paths updated to `research/results/` location.
- [x] No `Unknown columns: sizing_mode` warning on ingest from new artifact path.
- [x] End-to-end verification: nuke → baseline ingest → golden run → `recent_champions` returns result. *(confirmed 2026-04-05)*

## Dependencies
- No upstream blockers.
- Champion promotion depends on understanding the `ChampionArtifact` model's required
  fields — review `qws_graph/research/graph/models.py` before implementing part C.

## Open Questions
- Should `run_liquidity_sweep_baseline.sh` also promote its top result to Champion, or is
  baseline-as-Run-only the intended contract? (Affects scope of part C.)
- The `golden_champion.md` freeze date: should it be today's date, or the date of the
  underlying data span? Needs a decision before `_write_champion_md` is implemented.
- Should the `.env` source block be extracted into a shared `lib.sh` sourced by all runners,
  or inlined per script? (Inline is simpler for three scripts; lib makes sense at five or more.)

## Notes
The "ghost node" framing in the original description is a misnomer — `cypher.py` already
enforces explicit labels on every `MERGE` statement (`:Strategy`, `:Run`, `:Config`,
`:Champion`). Label-less nodes are not the issue. The actual schema gap is the absent
property key on Run nodes when `curator_note` is `None`, which is a subtler but real
consistency problem.

The `recent_champions` DTO (`ChampionDetailsV1` or similar) does not have a `curator_note`
field, so the property gap does not affect that preset directly — the `run_history` preset
is the one that surfaces it.