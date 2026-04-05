# Story — Centralized Ingestion Layer (Trial-to-Graph Bridge)

## ID
# QWS-0305

## Status
draft

## Priority
P2 — Maintainability. Every trial script independently constructs the graph-ingestable CSV by
hardcoding strategy metadata and manually mapping column names. Any schema change in
`qws_graph` (a new required column, a renamed alias, a tighter validator) requires touching
every trial file. There are currently three trial scripts with this pattern; more will follow.

## Summary
Extract the "trial output → graph-ingestable CSV" transformation into a shared utility module
(`research/graph_export.py` or a `qws_ingest` sub-package). Trial scripts pass their results
DataFrame and a strategy metadata dict; the utility validates, maps columns, and writes a CSV
the `qw record` parser can consume without further transformation.

## Problem
Each trial script contains a private `_write_baseline_csv` or `_write_graph_grid_csv` function
that independently:

1. **Hardcodes strategy metadata** — `instrument`, `timeframe`, `direction`, `logic_type` are
   duplicated in every file:
   ```python
   # 01_baseline.py, golden.py, 02_position_sizing.py — each independently:
   export["instrument"] = "CL"
   export["timeframe"] = "1H"
   export["direction"] = "bear"
   export["logic_type"] = "liquidity-sweep"
   ```

2. **Manually maps column names** — `n_trades` → `total_trades` is done inline in each file.
   The `qws_graph` parser (`parsers.py`) accepts `total_trades` or `n` as aliases for the
   required `total_trades` field (`CSV_REQUIRED_ALIASES`), but NOT `n_trades`. So the mapping
   is real and required — it is just duplicated:
   ```python
   export["total_trades"] = export["n_trades"]  # repeated in each trial
   ```

3. **Selects and filters `keep_cols` independently** — each trial maintains its own list of
   columns to retain. If a column is added to the parser's required set and one trial misses
   it, that trial silently produces a CSV that fails at ingest time.

The result: schema drift is invisible until `qw record` fails. The failure happens at record
time — after the trial has already completed — not at write time.

## Goal
Trial scripts call one function to produce a valid graph CSV:
```python
from research.graph_export import write_baseline_csv

write_baseline_csv(
    results_df,
    output_path=csv_path,
    instrument="CL",
    timeframe="1H",
    direction="bear",
    logic_type="liquidity-sweep",
)
```
All column mapping, metadata injection, and schema validation happen inside
`write_baseline_csv`. A missing required column raises immediately, before the CSV is written.

## Inputs
- `research/trials/futures/liquidity_sweep/01_baseline.py` — `_write_baseline_csv`
- `research/trials/futures/liquidity_sweep/golden.py` — `_write_golden_csv`
- `research/trials/futures/liquidity_sweep/02_position_sizing.py` — `_write_graph_grid_csv`
- `qws_graph/research/graph/parsers.py` — `CSV_REQUIRED_ALIASES`, `CSV_OPTIONAL_ALIASES`,
  `STRATEGY_COLUMNS`, `KNOWN_CONFIG_COLUMNS`
- `qws_graph/research/graph/models.py` — `Run`, `Strategy`, `Config` (the canonical schema)

## Proposed Design

### Module: `research/graph_export.py`
A single utility module. No new package, no install step — just a shared module under
`research/` consistent with existing layout (`research/experiments/`, `research/trials/`).

```python
# research/graph_export.py

COLUMN_ALIASES = {
    "n_trades": "total_trades",   # trial → parser name
    "n": "total_trades",
    # extend as needed
}

REQUIRED_FIELDS = {
    "instrument", "timeframe", "direction", "logic_type",
    "total_trades", "sharpe", "profit_factor", "win_rate", "max_drawdown",
}

def write_baseline_csv(
    df: pd.DataFrame,
    output_path: Path,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str,
    extra_cols: list[str] | None = None,
) -> Path:
    """Validate, inject metadata, and write a qw-compatible baseline CSV."""
    export = df.copy()

    # Rename aliases to canonical names.
    export = export.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in export.columns})

    # Inject strategy metadata.
    export["instrument"] = instrument
    export["timeframe"] = timeframe
    export["direction"] = direction
    export["logic_type"] = logic_type

    # Validate required fields before writing.
    missing = REQUIRED_FIELDS - set(export.columns)
    if missing:
        raise ValueError(f"Missing required graph export fields: {missing}")

    # Write.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(output_path, index=False)
    return output_path
```

A `write_grid_csv` variant handles grid sweeps (includes `params_json` serialization).

### Migration
Replace the three private `_write_*_csv` functions in trial scripts with calls to
`write_baseline_csv` / `write_grid_csv`. The output CSV is identical — only the source of
truth for schema mapping moves.

### Relationship to `qws_graph` Parser
`research/graph_export.py` derives its `REQUIRED_FIELDS` and `COLUMN_ALIASES` from
`qws_graph/research/graph/parsers.py::CSV_REQUIRED_ALIASES`. The two must stay in sync. A
comment in `graph_export.py` should point to the parsers file explicitly. A test that
imports both and compares required field sets would prevent silent drift.

## In Scope
- `research/graph_export.py` module with `write_baseline_csv` and `write_grid_csv`.
- Migration of `01_baseline.py`, `golden.py`, `02_position_sizing.py` to use the new module.
- Removal of the three private `_write_*_csv` functions from the trial files.
- Unit test: `write_baseline_csv` raises on missing required field before writing anything.
- Unit test: alias mapping (`n_trades` → `total_trades`) is applied correctly.

## Out of Scope
- Installing `qws_ingest` as a separate package (overkill for the current scale; revisit
  when there are 10+ trial families).
- Moving the `qw record` call into `graph_export` (shell scripts remain responsible for
  ingestion; this module only writes the file).
- Changes to `qws_graph/research/graph/parsers.py`.

## Repo Touchpoints
- `research/graph_export.py` — new file
- `research/trials/futures/liquidity_sweep/01_baseline.py`
- `research/trials/futures/liquidity_sweep/golden.py`
- `research/trials/futures/liquidity_sweep/02_position_sizing.py`
- `tests/unit/test_graph_export.py` — new test file

## Implementation Notes
- Keep `research/graph_export.py` dependency-free beyond `pandas` and `pathlib`. Do not
  import from `qws_graph` directly — that would create a cross-package dependency that
  makes the repo harder to run without the `qws_graph` install. Instead, keep the alias
  table maintained manually and tested for consistency.
- `direction` values accepted by the `Strategy` model are
  `Literal["long", "short", "bear", "bull"]` — validate this in `write_baseline_csv` to
  catch typos before write.
- The golden CSV currently omits several columns present in the baseline CSV (e.g.,
  `total_r`, `avg_r_per_trade`). `write_baseline_csv` should not require columns that are
  optional in the parser; only hard-fail on truly required fields.

## Acceptance Criteria
- [ ] `01_baseline.py`, `golden.py`, and `02_position_sizing.py` no longer contain private
  `_write_*_csv` functions.
- [ ] Calling `write_baseline_csv` with a DataFrame missing `sharpe` raises `ValueError`
  before any file is written.
- [ ] The CSV written by `write_baseline_csv` is accepted by `qw record --kind baseline_csv`
  without parser errors.
- [ ] Alias mapping: a DataFrame with `n_trades` column produces a CSV with `total_trades`.

## Validation
- Unit tests for `write_baseline_csv` with missing required fields, alias mapping, and
  metadata injection.
- Run `qw record --kind baseline_csv --file <output>` on the produced CSV as an integration
  check — parser should return no errors.

## Definition of Done
- [ ] `research/graph_export.py` implemented and tested.
- [ ] All three trial scripts migrated.
- [ ] Tests pass.
- [ ] No remaining `instrument = "CL"` hardcodes in trial scripts.

## Dependencies
- No upstream blockers.
- Should be implemented before adding new trial families to prevent the pattern from
  spreading further.

## Open Questions
- Should `write_baseline_csv` also accept a `strategy_id` override, or always derive it
  from instrument + timeframe + direction + logic_type (matching the parser's ID logic)?
- Should `COLUMN_ALIASES` in `graph_export.py` be generated from `CSV_REQUIRED_ALIASES`
  in `parsers.py` at import time (requires `qws_graph` install), or maintained as a
  static copy with a test asserting consistency?

## Notes
The "validate before the 2-hour backtest" framing from the story brief is imprecise for
the current trials (which run in seconds to minutes). The real value of early validation is
catching schema drift between trial output and the graph schema at write time, not at
record time. The fail-fast benefit is real — just not time-based.
