"""Schema registry for CSV ingestion column routing.

Single source of truth for which CSV columns belong on :Config vs :Run nodes.
Both the parser (validation) and the Cypher layer (property mapping) import
from here.  Adding a column to the right set is the only change needed to make
a new trial parameter queryable in the graph.

Config properties answer "how was this run configured?" (set before the run).
Run properties answer "how did this run perform?" (measured after the run).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Config properties
# ---------------------------------------------------------------------------

# Columns that belong on :Config — shared across all strategies.
CORE_CONFIG_PROPERTIES: set[str] = {
    "allowed_dir",
    "allowed_sessions",
    "chain_mode",
    "label",
    "max_hold_bars",
    "min_r_dist",
    "sessions",
    "sizing_mode",
    "sweep_timeframe",
    "target_r",
    "wick_mode",
}

# Config columns that are routed into the risk_params sub-dict.
# These are also first-class Config node properties — routing here is
# additive (they land in both params_json and risk_params blobs).
CORE_RISK_PARAM_COLUMNS: set[str] = {
    "atr_mult_stop",
    "lh_buffer_mult",
    "lh_lookback",
    "partial_exit_r",
    "stall_bars",
    "stall_threshold",
    "stop_mode",
}

# Strategy-specific config columns keyed by normalized logic_type.
# Keys must match the normalized logic_type produced by parsers._resolve_strategy
# (lowercase, hyphens instead of underscores).
STRATEGY_EXTENSIONS: dict[str, set[str]] = {
    "mars": {"atr_period", "mom_period", "trend_period", "vol_threshold"},
    "liquidity-sweep": {"time_stop"},
}


def get_config_keys(logic_type: str | None = None) -> set[str]:
    """Return the full set of recognized Config column names for a logic_type.

    Includes CORE_CONFIG_PROPERTIES, CORE_RISK_PARAM_COLUMNS, and any
    strategy-specific extensions for the given logic_type.
    """
    keys = set(CORE_CONFIG_PROPERTIES) | CORE_RISK_PARAM_COLUMNS
    if logic_type and logic_type in STRATEGY_EXTENSIONS:
        keys.update(STRATEGY_EXTENSIONS[logic_type])
    return keys


def all_config_keys() -> set[str]:
    """Return all known Config column names across all strategies.

    Used by the parser to classify columns without knowing the logic_type
    upfront (e.g., during header-level validation).
    """
    keys = set(CORE_CONFIG_PROPERTIES) | CORE_RISK_PARAM_COLUMNS
    for extension in STRATEGY_EXTENSIONS.values():
        keys.update(extension)
    return keys


# ---------------------------------------------------------------------------
# Run properties
# ---------------------------------------------------------------------------

# Columns that belong on :Run (result metrics — measured after the run).
# Core result metrics (sharpe, win_rate, etc.) are defined on the Run model
# directly; this set covers additional optional result columns.
RUN_PROPERTIES: set[str] = {
    "calmar",
    "return",   # CSV column name; stored as Run.metrics_return (reserved word)
    "tier",
}

# ---------------------------------------------------------------------------
# Ignored columns
# ---------------------------------------------------------------------------

# Housekeeping or derivative columns that should be silently accepted but not
# stored in any node.  These will NOT produce an "Unknown columns" warning.
IGNORED_COLUMNS: set[str] = {
    "avg_risk_pct",
    "beat_bh",
    "bh_exposure_return",
    "breakeven_win_rate",
    "exposure_frac",
    "fee_pct_of_gain",
    "fees",
    "gain",
    "max_hours_in_market",
    "outperformance_x",
    "sample_size",
    "total_hours",
    "mode",
    "risk_avg"
}
