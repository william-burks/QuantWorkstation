# QWS-HF-001 — Auto-link hypothesis from bundle manifest on ingest

## Status
READY

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

- [ ] `qw record --bundle <dir>` reads `hypothesis_id` from `bundle.json`
- [ ] TESTED_AS edge is created automatically if the hypothesis exists in the graph
- [ ] If hypothesis does not exist, a WARNING is printed (not an error — ingest still succeeds)
- [ ] Dry-run mode does not write the edge
- [ ] E2E test case added: bundle with `hypothesis_id` → TESTED_AS edge present in graph

## Repo Touchpoints
- `qws_graph/research/graph/cli.py` — `_cmd_bundle`: read `hypothesis_id` from manifest, call `store.link_hypothesis_tested_as` after ingest
- `qws_graph/tests/integration/test_cli_record_reconcile.py` — add E2E test: bundle with `hypothesis_id` → TESTED_AS edge present

## Out of Scope

- Validating hypothesis_id format at bundle write time
- Backfilling existing ingested bundles

## Definition of Done
- [ ] All ACs passing
- [ ] Tests green
- [ ] Story marked CLOSED
