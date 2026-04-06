"""Utility for writing qw-compatible graph CSV artifacts from trial output.

Trial scripts call write_baseline_csv or write_grid_csv to produce a CSV
accepted by `qw record --kind baseline_csv` / `--kind grid_csv`.

All column mapping, metadata injection, and schema validation happen here.
A missing required column raises ValueError before any file is written.

SYNC NOTE: REQUIRED_FIELDS mirrors CSV_REQUIRED_ALIASES in
qws_graph/research/graph/parsers.py::CSV_REQUIRED_ALIASES.
The test_graph_export_sync test in tests/unit/test_graph_export.py asserts
consistency between these two sets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Column aliases: trial output name -> canonical parser name
# Mirrors CSV_REQUIRED_ALIASES in qws_graph/research/graph/parsers.py
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, str] = {
    "n_trades": "total_trades",
    "n": "total_trades",
    "max_dd": "max_drawdown",
}

# ---------------------------------------------------------------------------
# Required fields (strategy metadata + core run metrics)
# Must match the required set of qws_graph CSV parser.
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: frozenset[str] = frozenset({
    "instrument",
    "timeframe",
    "direction",
    "logic_type",
    "total_trades",
    "sharpe",
    "profit_factor",
    "win_rate",
    "max_drawdown",
})

VALID_DIRECTIONS: frozenset[str] = frozenset({"long", "short", "bear", "bull"})


def _apply_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Rename alias columns to canonical parser names (in-place on copy)."""
    renames = {k: v for k, v in COLUMN_ALIASES.items() if k in df.columns}
    return df.rename(columns=renames)


def _inject_metadata(
    df: pd.DataFrame,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str,
) -> pd.DataFrame:
    df = df.copy()
    df["instrument"] = instrument
    df["timeframe"] = timeframe
    df["direction"] = direction
    df["logic_type"] = logic_type
    return df


def _validate(df: pd.DataFrame, direction: str, output_path: Path) -> None:
    if direction not in VALID_DIRECTIONS:
        raise ValueError(
            f"Invalid direction {direction!r}. Must be one of {sorted(VALID_DIRECTIONS)}."
        )
    missing = REQUIRED_FIELDS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required graph export fields for {output_path.name}: {sorted(missing)}"
        )


def write_baseline_csv(
    df: pd.DataFrame,
    output_path: Path,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str,
    extra_cols: list[str] | None = None,
) -> Path:
    """Validate, inject metadata, and write a qw-compatible baseline CSV.

    Raises ValueError before writing if any required field is absent.
    Returns output_path on success.
    """
    if df.empty:
        raise ValueError(f"DataFrame is empty; nothing to write to {output_path}.")

    export = _apply_aliases(df.copy())
    export = _inject_metadata(export, instrument, timeframe, direction, logic_type)
    _validate(export, direction, output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(output_path, index=False)
    return output_path


def write_grid_csv(
    df: pd.DataFrame,
    output_path: Path,
    instrument: str,
    timeframe: str,
    direction: str,
    logic_type: str,
) -> Path:
    """Validate, inject metadata, and write a qw-compatible grid CSV.

    For grid sweeps the DataFrame is expected to already contain per-row
    metrics (win_rate, profit_factor, total_trades, sharpe, max_drawdown).
    If a params_json column is present it is serialized to a JSON string;
    if the column value is already a string it is passed through unchanged.

    Raises ValueError before writing if any required field is absent.
    Returns output_path on success.
    """
    if df.empty:
        raise ValueError(f"DataFrame is empty; nothing to write to {output_path}.")

    export = _apply_aliases(df.copy())
    export = _inject_metadata(export, instrument, timeframe, direction, logic_type)

    # Serialize params_json dicts to strings if needed.
    if "params_json" in export.columns:
        export["params_json"] = export["params_json"].apply(
            lambda v: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v
        )

    _validate(export, direction, output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(output_path, index=False)
    return output_path
