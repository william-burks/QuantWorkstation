# Story — Algorithmic Promotion Threshold

## Status
draft

## Priority
P3 — Research workflow automation. Currently champion promotion is entirely manual: a human
decides when to run the golden script and then decides when to call `qw record --kind
champion_md`. The tier system in `research/experiments/standards.py` already defines
objective thresholds (SHARPE, PROFIT_FACTOR, CALMAR, MAX_DRAWDOWN_LIMIT) — this story
closes the gap between a passing tier and an automatic promotion candidate.

## Summary
After a trial CSV is ingested, evaluate the resulting Run node against configurable
promotion thresholds. If the thresholds are met, automatically generate a `champion_md`
artifact and print a prompt (or optionally auto-ingest it). The operator remains in the
loop for final approval, but the decision surface is explicit and rule-based rather than
ad hoc.

## Problem
The current workflow requires manual intervention at two points:

1. Deciding to run `run_liquidity_sweep_golden.sh` at all (currently: human inspects
   `index.html` and judges whether results are worth promoting).
2. Calling `qw record --kind champion_md` after generating the golden run.

There are no written-down promotion criteria. The tier thresholds in `standards.py`
classify runs as `pass`, `professional`, or `institutional`, but that classification
never triggers any downstream action automatically. A run that scores `professional` may
or may not be promoted depending on who is looking.

This introduces:
- **Human bias** — the bar shifts depending on context.
- **Missed promotions** — a run that clears the threshold may be forgotten if the operator
  doesn't review the HTML report.
- **Undocumented criteria** — there is no auditable record of why one run was promoted and
  another was not.

**Constraint: `Champion` model requirements.** Automatic promotion is not trivial. The
`Champion` model (`qws_graph/research/graph/models.py`) requires:
- `fragilities: list[str]` — must be non-empty (validated by `model_validator`).
- `oos_status: str` — must be set explicitly.
- `metrics_summary: dict` — must be non-empty.
- `freeze_date: date`.

A backtest result alone does not produce `fragilities` or `oos_status`. These require
either human input, AI curation, or a defined default (e.g., `fragilities = ["No OOS
validation performed"]`, `oos_status = "PENDING"`). Auto-generated champions must use
explicit defaults and be clearly marked as unreviewed.

## Goal
- Define promotion thresholds in a config file (`promotion_rules.yaml`).
- After `qw record --kind baseline_csv` succeeds, check the ingested Run against the rules.
- If thresholds are met: generate a `champion_md` draft artifact, print a promotion notice,
  and (optionally with `--auto-promote`) ingest it immediately.
- Generated champion drafts use explicit defaults for fields that require human/AI input,
  marked clearly as unreviewed.

## Inputs
- `qws_graph/research/graph/cli.py` — `record` subcommand (post-ingest hook point)
- `qws_graph/research/graph/models.py` — `Champion` model and its validators
- `qws_graph/research/graph/parsers.py` — `ChampionMarkdownParser` (for the inverse: writing)
- `qws_graph/research/graph/store.py` — `persist_artifact` for champion ingest
- `research/experiments/standards.py` — existing tier thresholds (the source of truth for
  numeric thresholds; `promotion_rules.yaml` must not contradict these)
- `research/experiments/evaluator.py` — `tier()` function

## Proposed Design

### Promotion Rules File: `qws_graph/promotion_rules.yaml`
```yaml
# Promotion thresholds for auto-champion-draft generation.
# All conditions must be met for a Run to qualify.
# Numeric thresholds must be at or above standards.py tier levels.
promotion:
  min_sharpe: 1.5           # SHARPE["professional"] — do not set below SHARPE["pass"] = 0.8
  min_profit_factor: 1.75   # PROFIT_FACTOR["professional"]
  max_drawdown_floor: -0.10 # stricter than MAX_DRAWDOWN_LIMIT (-0.20) — tune as needed
  min_trades: 30            # above MIN_TRADES_PER_YEAR (12) floor

champion_defaults:
  oos_status: "PENDING"
  fragilities:
    - "No OOS validation performed — auto-generated draft"
    - "Promoted by algorithmic threshold, not reviewed"
```

The thresholds in `promotion_rules.yaml` should be treated as a floor on top of
`standards.py`. They must not be set below the `pass` tier values in `standards.py` or
the hard `MAX_DRAWDOWN_LIMIT` (`-0.20`). A validation step at load time should assert this.

### Post-Ingest Evaluation Hook
After a successful `baseline_csv` or `grid_csv` ingest in `cli.py`, evaluate each
persisted `Run` against the loaded promotion rules:

```python
from .promotion import evaluate_promotion_candidates

candidates = evaluate_promotion_candidates(run_nodes, rules)
if candidates:
    for run in candidates:
        draft_path = write_champion_draft(run, rules)
        print(f"PROMOTION CANDIDATE: {run.run_id}")
        print(f"  Draft written: {draft_path}")
        print(f"  Review and ingest: qw record --kind champion_md --file {draft_path}")
```

### `--auto-promote` Flag
Optional flag on `qw record`. When set, qualifying runs are ingested as champions
immediately after the CSV ingest, without a separate `qw record --kind champion_md` call.
The draft `champion_md` file is still written to disk for auditability.

Without `--auto-promote`, the default is to print the promotion candidate notice and write
the draft — human runs `qw record --kind champion_md --file <draft>` to confirm.

### Champion Draft Generation: `research/graph/promotion.py`
```python
def write_champion_draft(run: Run, rules: PromotionRules, output_dir: Path) -> Path:
    """Write a champion.md draft for operator review or auto-ingest."""
    # Sets fragilities and oos_status from rules.champion_defaults.
    # Sets metrics_summary from Run metrics.
    # Sets freeze_date to today.
    # Sets pivot_from_run_id to run.run_id.
    ...
```

The generated markdown must pass `ChampionMarkdownParser` validation — this is the
acceptance gate, not a separate validator.

## In Scope
- `qws_graph/promotion_rules.yaml` — new config file with documented thresholds.
- `qws_graph/research/graph/promotion.py` — threshold evaluation and draft generation.
- Post-ingest hook in `qws_graph/research/graph/cli.py` — evaluate after successful write.
- `--auto-promote` flag on `qw record`.
- Validation: loaded thresholds must not be less strict than `standards.py` hard limits.
- Unit tests for threshold evaluation and draft generation.

## Out of Scope
- Modifying `standards.py` thresholds (those are the research tier standards; promotion
  thresholds are a separate concern and live in `promotion_rules.yaml`).
- AI-generated `fragilities` or `oos_status` (that is the AI curation pipeline's job;
  this story uses explicit static defaults).
- Auto-triggering the golden trial script from a baseline promotion — the golden run is
  a separate deliberate step.
- Promotion based on grid-sweep aggregate stats (only individual Run nodes are evaluated).

## Repo Touchpoints
- `qws_graph/promotion_rules.yaml` — new
- `qws_graph/research/graph/promotion.py` — new
- `qws_graph/research/graph/cli.py` — post-ingest hook, `--auto-promote` flag
- `qws_graph/research/graph/models.py` — read-only (no changes)
- `research/experiments/standards.py` — read-only (threshold validation imports from here)
- `tests/unit/test_promotion.py` — new

## Implementation Notes
- The `Champion` model's `model_validator` asserts `fragilities` is non-empty and
  `metrics_summary` is non-empty. The draft generator must satisfy both. Using
  `["No OOS validation performed — auto-generated draft"]` as the default fragility list
  is sufficient and honest.
- `freeze_date` should be today's date (`date.today()`), not the run timestamp. The freeze
  date represents when the decision was made, not when the backtest ran.
- `champion_id` is derived by the `ids.py` `champion_id()` function — the draft generator
  should use that, not invent its own.
- `oos_status` of `"PENDING"` must be a valid value in any downstream query that filters
  on it. Check `query.py` for any `WHERE ch.oos_status = ...` patterns before choosing
  the default string.
- Do not evaluate promotion on `grid_csv` ingests by default — grid sweeps contain many
  runs with varying parameters; promotion logic for grids is a separate, more complex
  problem (which run wins? how do you pick the `config`?).

## Acceptance Criteria
- [ ] After ingesting a Run with Sharpe = 1.8, profit_factor = 2.0, max_drawdown = -0.08,
  and total_trades = 45: promotion candidate notice is printed and `champion_draft.md` is
  written.
- [ ] After ingesting a Run with Sharpe = 0.9 (below `min_sharpe`): no candidate notice.
- [ ] `promotion_rules.yaml` with `min_sharpe: 0.5` (below `SHARPE["pass"] = 0.8`) raises
  a validation error at load time.
- [ ] `qw record --auto-promote --kind baseline_csv --file results.csv` results in both a
  `Run` node and a `Champion` node in the graph for a qualifying run.
- [ ] The generated `champion_draft.md` passes `ChampionMarkdownParser` without errors.

## Validation
- Unit test: `evaluate_promotion_candidates` returns correct subset of runs given mixed
  qualifying/non-qualifying inputs.
- Unit test: `write_champion_draft` output parses cleanly through `ChampionMarkdownParser`.
- Unit test: threshold validation raises when `promotion_rules.yaml` contains a value
  below `standards.py` hard limits.
- Integration: full flow — ingest qualifying CSV with `--auto-promote`, confirm Run +
  Champion nodes in Neo4j, confirm `qw query --name recent_champions` returns the champion.

## Definition of Done
- [ ] `promotion_rules.yaml` with documented thresholds.
- [ ] `promotion.py` implemented and tested.
- [ ] Post-ingest hook live in `cli.py`.
- [ ] `--auto-promote` flag functional.
- [ ] `qw query --name recent_champions` returns auto-promoted champions without manual
  intervention.
- [ ] Story marked CLOSED after integration test passes.

## Dependencies
- Depends on: the `champion_md` ingest path must be fully functional (Story —
  Graph Ingestion Schema Consistency: champion promotion fix is a prerequisite).
- The `ChampionMarkdownParser` must be able to round-trip a programmatically generated
  markdown file — verify before implementing `write_champion_draft`.

## Open Questions
- Should `--auto-promote` be opt-in (flag required) or opt-out (`--no-promote` to
  suppress)? Opt-in is safer for the first implementation.
- Should qualifying-but-not-auto-promoted candidates be written to a `pending_champions/`
  directory, or inline next to the ingest artifact?
- Is `oos_status = "PENDING"` the right string, or does the query layer expect a specific
  enum value? Audit `query.py` before deciding.
- Should the promotion check run on re-ingests (idempotent MERGE of existing Run nodes),
  or only on first ingest? Running on every ingest risks generating duplicate draft files.

## Notes
The threshold values in the story brief (Sharpe > 2.0, MaxDD < 5%) differ from the
existing tier thresholds in `standards.py`. Sharpe > 2.0 sits between `professional`
(1.5) and `institutional` (2.5); MaxDD < 5% is far stricter than `MAX_DRAWDOWN_LIMIT`
(-20%). These numbers are design choices, not facts — the implementer should set
thresholds deliberately in `promotion_rules.yaml` with reference to the actual tier
boundaries, not guess from the brief.
