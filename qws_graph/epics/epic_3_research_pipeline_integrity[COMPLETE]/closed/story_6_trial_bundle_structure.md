# Story — Trial Bundle: Co-located Artifacts per Run

## ID
# QWS-0306

## Status
CLOSED

## Priority
P3 — Organization. Currently only CSVs are ingested to the graph; HTML reports and any
supporting markdown are generated to a flat directory and silently orphaned. Artifact
co-location becomes important once there are multiple trial variants producing overlapping
filenames in the same directory, or when an operator needs to reconstruct which HTML report
corresponds to which graph Run node.

## Summary
Define a standard per-run output directory structure so all artifacts produced by a trial
(CSV, HTML, supporting markdown) are co-located and traceable. Add a `qw record --bundle
<dir>` flag that reads a `bundle.json` manifest and ingests all recognized artifacts from
a bundle directory in the correct order.

## Problem
The liquidity sweep trial currently writes all output to a flat directory
(`research/results/futures/liquidity_sweep/`):

```
baseline_results.csv
index.html
golden_results.csv
golden.html
position_sizing_results.csv
position_sizing_equity_curves.csv
position_sizing_summary.json
position_sizing.html
```

**What is actually ingested to the graph**: only the CSVs. The shell runner calls
`qw record --file baseline_results.csv --kind baseline_csv`. The HTML files are
written but never passed to `qw record` — they are already orphaned, not at risk
of orphaning.

**What this creates**:
1. No linkage between a `Run` node in the graph and the HTML report for that run. An
   operator querying `qw query --name run_history` cannot navigate to the visual report.
2. Filename collisions as new trials are added. A second trial writing `index.html` or
   `results.csv` to the same directory overwrites the previous run's artifacts silently.
3. No way to reproduce "which config produced which report" without cross-referencing
   timestamps or manually reading file contents.

**Note on `run_id`**: The `run_id` is generated deterministically by `parsers.py` from a
hash of the CSV content and provenance metadata — it is not known until after the file is
parsed. Output directories therefore cannot be named `{run_id}/` at write time. The
bundle structure must use a pre-run identifier (the shell runner's `RUN_TS`).

## Goal
- Each trial run writes artifacts to a timestamped subdirectory:
  `research/results/futures/liquidity_sweep/runs/{YYYYMMDD-HHMMSS}/`
- The CSV, HTML, and any supporting files for that run live together in that directory.
- The shell runner writes a `bundle.json` manifest after the trial script exits.
- `qw record --bundle <dir>` reads the manifest, ingests the CSV first, then patches
  the resulting Run node with the HTML artifact path.
- A completed bundle directory is self-contained: given only the directory, an operator
  can reconstruct the full run.

## Resolved Decisions

### 1. Where does `runs/` live?
**Decision: Local but Standardized.**
`runs/` lives inside each trial's results directory:
`research/results/<trial_family>/<trial_name>/runs/{ts}/`

Reasoning: Maintains the "Trial as a Package" philosophy. The graph provides the
cross-strategy view — we don't need a flat folder structure for that; Neo4j handles it.

### 2. Is `bundle.json` required?
**Decision: Required, no fallback detection.**
`qw record --bundle` strictly requires a `bundle.json`. If it's missing, the command
fails with a clear error. There is no auto-detection from filename or header.

Reasoning: Auto-detection by file extension or CSV header is "magic that eventually
breaks" — baseline vs grid cannot be reliably distinguished from filename alone, and
header detection duplicates the parser's own classification logic.

**Who writes the manifest:** The shell runner, not the trial script. The runner already
holds `RUN_TS`, knows which files the trial will produce, and can emit the manifest as
a simple heredoc after the Python script exits. Trial scripts remain dumb — they accept
`--output-dir` and write files there.

### 3. Are `report_html` blobs stored in Neo4j?
**Decision: Path-only property on `:Run`.**
Store the absolute (or repo-relative) path as `artifact_path_html` on the `:Run` node.
Do not create a `BlobArtifact` node for the HTML file.

Reasoning: The UI can serve the file directly from the local filesystem. The graph holds
the pointer, not the content. This keeps the graph lean and avoids a BlobArtifact schema
change that would add overhead without a concrete graph query benefit.

**Two-phase write consequence:** `run_id` is not known until the CSV is parsed. The CLI
must:
1. Ingest CSV → receive `run_id`.
2. Call `Store.patch_run_html_path(run_id, path)` to attach the HTML pointer.

### 4. `is_bundled` flag in the store?
**Decision: Withdrawn.**
Receipt formatting is the CLI's responsibility. The store ingests (data-in, node-out)
and patches. No bundle semantics leak into the store layer.

## Inputs
- `research/run_liquidity_sweep_baseline.sh` — **does not exist yet; new file**
- `research/run_liquidity_sweep_golden.sh` — **does not exist yet; new file**
- `research/run_liquidity_sweep_position_sizing.sh` — **does not exist yet; new file**
- `research/trials/futures/liquidity_sweep/01_baseline.py` — hardcoded output paths
- `research/trials/futures/liquidity_sweep/golden.py` — same pattern
- `research/trials/futures/liquidity_sweep/02_position_sizing.py`
- `qws_graph/research/graph/cli.py` — `record` subcommand, `record_parser` (add `--bundle`)
- `qws_graph/research/graph/store.py` — new `patch_run_html_path` method
- `qws_graph/research/graph/cypher.py` — new `PATCH_RUN_HTML_PATH_QUERY`
- `qws_graph/research/graph/models.py` — `Run.artifact_path_html` (optional field)

## Proposed Design

### Bundle Directory Layout
```
research/results/futures/liquidity_sweep/runs/
  20260405-143022/
    baseline_results.csv    ← graph-ingestable CSV (required by bundle.json)
    report.html             ← visual report (optional, linked via patch)
    bundle.json             ← manifest written by shell runner after trial exits
```

### Bundle Manifest (`bundle.json`)
Written by the shell runner using a heredoc after the trial script exits successfully:
```json
{
  "trial": "liquidity_sweep_baseline",
  "run_ts": "20260405-143022",
  "files": {
    "csv": "baseline_results.csv",
    "csv_kind": "baseline_csv",
    "html": "report.html"
  }
}
```

Fields:
- `trial`: human-readable trial name (informational only)
- `run_ts`: directory timestamp (matches directory name)
- `files.csv`: filename of the graph-ingestable CSV (required)
- `files.csv_kind`: `baseline_csv` or `grid_csv` (required — passed to `CSVParser`)
- `files.html`: filename of the HTML report (optional — omit if not produced)

### Store API: `patch_run_html_path`
New idempotent method on `Store`:
```python
def patch_run_html_path(self, run_id: str, html_path: str) -> None:
    """Attach an HTML report path to an existing Run node."""
```
Backed by `PATCH_RUN_HTML_PATH_QUERY` in `cypher.py`:
```cypher
MATCH (r:Run {run_id: $run_id})
SET r.artifact_path_html = $html_path,
    r.updated_at = datetime()
```

### Model Change Required
`Run` in `models.py` needs:
```python
artifact_path_html: str | None = None
```

### CLI: `qw record --bundle <dir>`
- `--bundle` and `--file` are mutually exclusive in argparse.
- Reads `bundle.json` from the directory; fails with clear error if absent.
- Resolves CSV path: `<dir>/<files.csv>`.
- Calls existing `CSVParser` + `Store._persist_csv` with `kind=files.csv_kind`.
- Captures returned `run_id` from the ingest receipt.
- If `files.html` is present, resolves the absolute path and calls
  `Store.patch_run_html_path(run_id, html_path)`.
- Prints a single bundle receipt: `run_id`, all artifact paths, patch status.

### Trial Script Changes
Each trial script gains an `--output-dir` CLI argument (default: existing flat path for
backward compat). When provided, all outputs (CSV, HTML) are written to that directory
instead of the hardcoded path.

### Shell Runner Changes
Each shell runner:
1. Assigns `RUN_TS=$(date +%Y%m%d-%H%M%S)` at the top.
2. Constructs `RUN_DIR=research/results/.../runs/${RUN_TS}` and `mkdir -p "$RUN_DIR"`.
3. Passes `--output-dir "$RUN_DIR"` to the Python trial script.
4. After the script exits successfully, writes `bundle.json` via heredoc.
5. Prints the bundle dir path and calls `qw record --bundle "$RUN_DIR"`.

## In Scope
- Shell runners: `RUN_TS` assignment, `--output-dir` forwarding, `bundle.json` generation.
- Trial scripts: `--output-dir` argument replacing hardcoded paths.
- `bundle.json` manifest format (fields defined above).
- `qw record --bundle <dir>` CLI flag in `cli.py`.
- `Store.patch_run_html_path` + `PATCH_RUN_HTML_PATH_QUERY`.
- `Run.artifact_path_html` optional field in `models.py`.
- Unit tests: bundle reader, missing manifest error, patch method.

## Out of Scope
- `BlobArtifact` node for HTML (path property on Run is sufficient).
- Ingesting `position_sizing_equity_curves.csv` or `position_sizing_summary.json` as
  graph artifacts (intermediate files, not primary results).
- Versioning, retention policy, or cleanup of old `runs/` directories.
- Backward compat removal of the flat output directory (flat output remains the default
  when `--output-dir` is not passed; existing `qw record --file` path unchanged).

## Repo Touchpoints
- `research/run_liquidity_sweep_baseline.sh` — **new file**
- `research/run_liquidity_sweep_golden.sh` — **new file**
- `research/run_liquidity_sweep_position_sizing.sh` — **new file**
- `research/trials/futures/liquidity_sweep/01_baseline.py` — add `--output-dir`
- `research/trials/futures/liquidity_sweep/golden.py` — add `--output-dir`
- `research/trials/futures/liquidity_sweep/02_position_sizing.py` — add `--output-dir`
- `qws_graph/research/graph/cli.py` — `--bundle` flag + orchestration
- `qws_graph/research/graph/store.py` — `patch_run_html_path`
- `qws_graph/research/graph/cypher.py` — `PATCH_RUN_HTML_PATH_QUERY`
- `qws_graph/research/graph/models.py` — `Run.artifact_path_html`
- `qws_graph/tests/unit/` — bundle parsing, missing manifest error, patch method

## Implementation Notes
- `run_id` is content-addressed (hash of CSV + provenance) — it cannot be the bundle
  directory name. Use `run_ts` (write time) as the directory name.
- `--bundle` and `--file` must be mutually exclusive in argparse. Adding a `--bundle`
  flag while keeping `--file` unchanged preserves backward compat for all existing
  shell scripts that have not been migrated yet.
- `patch_run_html_path` must be idempotent — repeated calls with the same path are safe.
  Repeated calls with a different path overwrite; this is intentional (re-run replaces).
- Trial scripts should default `--output-dir` to the existing flat path so that running
  a trial manually (without the shell runner) continues to work without changes.
- The shell runner's `bundle.json` heredoc should be in the runner, not inside a
  separate Python helper, to keep the trial script's Python dependency surface minimal.

## Acceptance Criteria
- [x] Running `run_liquidity_sweep_baseline.sh` produces
  `runs/<timestamp>/baseline_results.csv` and `runs/<timestamp>/report.html`
  (no flat-directory collision risk for new runs).
- [x] `bundle.json` exists in the run directory with `trial`, `run_ts`, and `files`
  fields populated by the shell runner.
- [x] `qw record --bundle runs/<timestamp>` ingests the CSV and patches the Run node
  with `artifact_path_html` without manual intervention.
- [x] `qw record --bundle` receipt includes the `run_id` generated post-parse.
- [x] `qw record --bundle <dir>` fails with a clear error if `bundle.json` is absent
  (no silent skip, no auto-detection fallback).
- [x] `qw record --file` (existing path) is unaffected — backward compat confirmed.

## Validation
- Unit test: `bundle.json` reader returns expected file mappings.
- Unit test: `qw record --bundle` on a directory without `bundle.json` raises with
  a message that names the expected file.
- Unit test: `patch_run_html_path` issues the correct Cypher with the correct params.
- Manual end-to-end: run baseline shell runner, check directory structure, run
  `qw record --bundle`, confirm `Run.artifact_path_html` set in Neo4j.

## Definition of Done
- [x] Bundle directory layout implemented (shell runners + trial script `--output-dir`).
- [x] `bundle.json` generated by shell runners.
- [x] `qw record --bundle` implemented in `cli.py`.
- [x] `Store.patch_run_html_path` implemented and tested.
- [x] `Run.artifact_path_html` added to model.
- [x] All three shell runners produce bundled output.
- [x] All three trial scripts accept `--output-dir`.

## Dependencies
- Story 5 (Centralized Ingestion Layer) — complete. The `--output-dir` parameterization
  is cleaner now that trial scripts use `write_baseline_csv` from `graph_export.py`
  rather than hardcoded internal functions.
- Independent of: champion promotion story.

## Implementation Order
Start with the **Store/CLI layer** (`patch_run_html_path` + `--bundle` flag) before
touching the shell runners. Reason: the store method and CLI flag can be fully unit-tested
against fixture directories without running any trial. Shell runner changes are last — they
are thin wrappers that only combine already-tested pieces.

Sequence:
1. `models.py` — add `Run.artifact_path_html`
2. `cypher.py` — add `PATCH_RUN_HTML_PATH_QUERY`
3. `store.py` — add `patch_run_html_path`
4. `cli.py` — add `--bundle` flag and orchestration
5. Trial scripts — add `--output-dir` to each
6. Shell runners — `RUN_TS`, directory creation, manifest generation

## Open Questions
*(none — all resolved above)*
