# QWS-HF-001 — Auto-link hypothesis from bundle manifest on ingest

## Status
TESTING

## Type
code

## Discovered
2026-04-12 — surfaced during QWS-0901 first research session (liquidity sweep walk-forward)

## Problem

When `bundle.json` contains a `hypothesis_id` field, `qw record --bundle` ignores it:

```
WARNING: Unknown columns in baseline_results.csv: hypothesis_id
```

The TESTED_AS edge between the Hypothesis node and the Strategy must be created
manually after ingestion:

```bash
qw record --hypothesis a0e7380e58e8 --tested-as cl-1h-bear-liquidity-sweep
```

This breaks the workflow. The researcher logs a hypothesis, runs a trial, writes the
hypothesis ID into bundle.json — and expects the graph to wire up automatically. Instead
they get a silent warning and a dangling hypothesis with no strategy link.

## Root Cause

`_cmd_bundle` in `qws_graph/research/graph/cli.py` reads only `files` from the bundle
manifest. It does not read `hypothesis_id` even though trial scripts already write it.

## Fix

In `_cmd_bundle`, after a successful ingest, check for `hypothesis_id` in the manifest.
If present and the ingest succeeded (not a dry run), call `store.link_hypothesis_tested_as`
with the strategy_id from the ingested artifact.

```python
hypothesis_id = manifest.get("hypothesis_id")
if hypothesis_id and not dry_run and ingest_ok:
    linked = store.link_hypothesis_tested_as(hypothesis_id, artifact.strategy.strategy_id)
    if linked:
        print(f"OK: TESTED_AS edge — hypothesis={hypothesis_id} strategy={artifact.strategy.strategy_id}")
    else:
        print(f"WARNING: hypothesis {hypothesis_id!r} not found — TESTED_AS edge skipped", file=sys.stderr)
```

## Acceptance Criteria

- [x] `qw record --bundle <dir>` reads `hypothesis_id` from `bundle.json`
- [x] TESTED_AS edge is created automatically if the hypothesis exists in the graph
- [x] If hypothesis does not exist, a WARNING is printed (not an error — ingest still succeeds)
- [x] Dry-run mode does not write the edge
- [x] E2E test case added: bundle with `hypothesis_id` → TESTED_AS edge present in graph

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — `_cmd_bundle`: read `hypothesis_id` from manifest, call `store.link_hypothesis_tested_as` after ingest; `_cmd_hypothesis`: create Hypothesis node before BRANCHED_FROM edge when `--hypothesis` is a title string
- `qws_graph/tests/integration/test_cli_record_reconcile.py` — add E2E test: bundle with `hypothesis_id` → TESTED_AS edge present; add E2E test: single-call `--hypothesis <title> --branched-from <id>` creates both node and edge

## Out of Scope

- Validating hypothesis_id format at bundle write time
- Backfilling existing ingested bundles
- Validating that `--branched-from` parent ID exists before node creation

---

## Fix 2 — GAP-010: `_cmd_hypothesis` missing node creation on combined `--hypothesis` + `--branched-from`

### Problem

`_cmd_hypothesis` in `cli.py` creates the BRANCHED_FROM edge but NOT the Hypothesis node when called as:

```bash
qw record --hypothesis "new hypothesis title" --branched-from <parent_id>
```

`--hypothesis` is interpreted as a title string (not a 12-char ID) but the node-creation step is skipped — only the edge write is attempted. The edge write silently fails or targets a non-existent node.

### Fix

In `_cmd_hypothesis`, when `--hypothesis` value is a title string (len != 12 or not hex) and `--branched-from` is provided, create the Hypothesis node first in the same transaction, then create the BRANCHED_FROM edge using the new node's ID.

```python
# Pseudocode for combined path
if branched_from and not _looks_like_id(hypothesis_arg):
    node_id = store.create_hypothesis(title=hypothesis_arg)
    store.create_branched_from_edge(child=node_id, parent=branched_from)
    print(f"OK: Hypothesis created — id={node_id}")
    print(f"OK: BRANCHED_FROM edge — {node_id} → {branched_from}")
```

### Acceptance Criteria (Fix 2)

- [x] `qw record --hypothesis "new title" --branched-from <parent_id>` creates the Hypothesis node AND the BRANCHED_FROM edge in a single call
- [x] If `--hypothesis` is a 12-char hex ID (existing node), behavior is unchanged — only the edge is created
- [x] If `--branched-from` parent does not exist, command exits with non-zero and prints an error
- [x] E2E test: single call with title + `--branched-from` → both node and edge present in graph

## Definition of Done
- [x] All ACs passing (Fix 1 + Fix 2)
- [x] Tests green
- [ ] Story marked CLOSED — requires manual close after verify

## Acceptance Test Plan

### AC1: bundle reads hypothesis_id and calls link_hypothesis_tested_as
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestBundleHypothesisAutolink::test_bundle_with_hypothesis_id_calls_link -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC2: TESTED_AS edge created when hypothesis exists
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestBundleHypothesisAutolink::test_bundle_with_hypothesis_id_calls_link -v`
- expect_contains: "link_hypothesis_tested_as"
- expect_exit: 0

### AC3: hypothesis not found → WARNING, ingest still succeeds (exit 0)
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestBundleHypothesisAutolink::test_bundle_hypothesis_not_found_warns_not_errors -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC4: dry-run does not write TESTED_AS edge
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestBundleHypothesisAutolink::test_bundle_dry_run_skips_link -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC5: title + --branched-from creates node then edge
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestHypothesisBranchedFromNodeCreation::test_title_plus_branched_from_creates_node_and_edge -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC6: 12-char hex ID + --branched-from skips node creation
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestHypothesisBranchedFromNodeCreation::test_existing_id_plus_branched_from_skips_node_creation -v`
- expect_contains: "PASSED"
- expect_exit: 0

### AC7: --branched-from parent not found → exit 1
- type: regression
- cmd: `pytest qws_graph/tests/integration/test_cli_record_reconcile.py::TestHypothesisBranchedFromNodeCreation::test_branched_from_target_not_found_returns_error -v`
- expect_contains: "PASSED"
- expect_exit: 0
