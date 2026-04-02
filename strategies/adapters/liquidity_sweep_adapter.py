"""Adapter for the legacy bear liquidity sweep backtest.

This keeps the original strategy logic intact while allowing runs from the
project's ArcticDB-backed research workflow.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from data.store import Store, get_store


def _load_legacy_module() -> Any:
    root = Path(__file__).resolve().parents[2]
    legacy_path = root / "bear_nypre_after_1h_no_smt_exclude_q2_v2.py"
    spec = importlib.util.spec_from_file_location("legacy_liquidity_sweep", legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy module from {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = _load_legacy_module()

_DEFAULT_SYMBOLS: dict[str, str] = {
    "cl5": "CL_continuous_5min",
    "cl1h": "CL_continuous_1H",
    "mes5": "MES_continuous_5min",
    "mnq5": "MNQ_continuous_5min",
}


def _normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Match the legacy script expectation: numeric columns + US/Eastern index."""
    out = df.copy()
    idx = pd.to_datetime(out.index, utc=True)
    out.index = idx.tz_convert("US/Eastern")
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_index()


def prepare_data_from_frames(
    cl5: pd.DataFrame,
    cl1h: pd.DataFrame,
    mes5: pd.DataFrame,
    mnq5: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build the data payload expected by legacy.run_backtest()."""
    cl5n = _normalize_bars(cl5)
    cl1hn = _normalize_bars(cl1h)
    mes5n = _normalize_bars(mes5)
    mnq5n = _normalize_bars(mnq5)

    cl5n["atr"] = legacy.compute_atr(cl5n)
    cl1hn["atr"] = legacy.compute_atr(cl1hn)

    cl5n["session"] = [legacy.label_session(i) for i in cl5n.index]
    cl1hn["session"] = [legacy.label_session(i) for i in cl1hn.index]

    cl1hn = legacy.swing_pivots(cl1hn)
    cl5n = legacy.detect_fvg(cl5n)
    cl5n = legacy.detect_ifvg(cl5n)

    return {
        "cl5": cl5n,
        "cl1h": cl1hn,
        "mes5": mes5n,
        "mnq5": mnq5n,
    }


def load_data_from_store(
    store: Store | None = None,
    symbols: Mapping[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Read required symbols from ArcticDB and prepare legacy inputs."""
    symbol_map = dict(_DEFAULT_SYMBOLS)
    if symbols:
        symbol_map.update(symbols)

    s = store or get_store()
    cl5 = s.read_bars("futures", symbol_map["cl5"])
    cl1h = s.read_bars("futures", symbol_map["cl1h"])
    mes5 = s.read_bars("futures", symbol_map["mes5"])
    mnq5 = s.read_bars("futures", symbol_map["mnq5"])
    return prepare_data_from_frames(cl5=cl5, cl1h=cl1h, mes5=mes5, mnq5=mnq5)


def run_from_store(
    config_overrides: Mapping[str, Any] | None = None,
    store: Store | None = None,
    symbols: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute the legacy backtest using bars loaded from Store."""
    data = load_data_from_store(store=store, symbols=symbols)
    return run_with_data(data=data, config_overrides=config_overrides)


def run_with_data(
    data: Mapping[str, pd.DataFrame],
    config_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the legacy backtest with preloaded/prepared data."""
    config = dict(legacy.DEFAULT_CONFIG)
    if config_overrides:
        config.update(dict(config_overrides))

    result = legacy.run_backtest(dict(data), config)
    return result


def loaded_rows(data: Mapping[str, pd.DataFrame]) -> dict[str, int]:
    """Return the row-count summary expected by legacy report printer."""
    return {k: len(v) for k, v in data.items()}


def print_report(result: Mapping[str, Any], data: Mapping[str, pd.DataFrame]) -> None:
    """Print the legacy strategy report with row counts from prepared data."""
    legacy.print_backtest_report(result, loaded_rows(data))



