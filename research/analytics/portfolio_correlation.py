"""Portfolio Correlation Analysis — QWS-0603.

Computes pairwise Pearson correlation across OOS-pass Champions using daily_pnl
or equity columns from artifact CSVs. Flags pairs above threshold. Writes
CORRELATED_WITH edges to the graph.

CSV pre-condition (discovered at implementation time):
    Current artifact CSVs are parameter-sweep results (one row per param combo).
    They do NOT contain daily_pnl or equity columns. Champions backed by such
    CSVs are skipped with a warning — graceful degradation per AC3.

Usage:
    python -m research.analytics.portfolio_correlation [--threshold 0.6]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 0.60
_PNL_COLUMNS = ("daily_pnl", "equity")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_pnl_series(artifact_path: str, repo_root: Path) -> pd.Series | None:
    """Load a daily P&L or equity series from *artifact_path*.

    Returns a ``pd.Series`` indexed by date when the CSV contains a
    ``daily_pnl`` or ``equity`` column. Returns ``None`` with a warning when:
    - the file does not exist
    - neither column is present
    - parsing fails
    """
    csv_path = repo_root / artifact_path
    if not csv_path.exists():
        warnings.warn(f"artifact not found: {artifact_path}", stacklevel=2)
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"failed to read {artifact_path}: {exc}", stacklevel=2)
        return None

    col: str | None = None
    for candidate in _PNL_COLUMNS:
        if candidate in df.columns:
            col = candidate
            break

    if col is None:
        warnings.warn(
            f"skipping {artifact_path}: no daily_pnl or equity column found "
            f"(columns: {list(df.columns)})",
            stacklevel=2,
        )
        return None

    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").set_index("date")
        except Exception:  # noqa: BLE001
            pass

    return df[col].astype(float)


# ---------------------------------------------------------------------------
# Correlation computation
# ---------------------------------------------------------------------------


def compute_correlation_matrix(
    series_map: dict[str, pd.Series],
) -> pd.DataFrame:
    """Return pairwise Pearson correlation matrix from aligned series."""
    if not series_map:
        return pd.DataFrame()
    combined = pd.DataFrame(series_map)
    return combined.corr(method="pearson")


def flag_high_pairs(
    corr_matrix: pd.DataFrame,
    threshold: float,
) -> list[tuple[str, str, float]]:
    """Return list of (label_a, label_b, coefficient) for |r| > threshold.

    Each pair appears once (upper triangle only).
    """
    pairs: list[tuple[str, str, float]] = []
    labels = list(corr_matrix.columns)
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            r = float(corr_matrix.loc[a, b])
            if abs(r) > threshold:
                pairs.append((a, b, r))
    return pairs


# ---------------------------------------------------------------------------
# Graph write
# ---------------------------------------------------------------------------


def write_correlated_with_edges(
    store: Any,
    champion_map: dict[str, dict[str, Any]],
    high_pairs: list[tuple[str, str, float]],
    threshold: float,
    lookback: str = "full",
) -> int:
    """Write CORRELATED_WITH edges to graph for each flagged pair.

    Args:
        store: GraphStore instance.
        champion_map: Mapping of label → champion dict (needs champion_id, strategy_id).
        high_pairs: Pairs returned by flag_high_pairs.
        threshold: Correlation threshold used.
        lookback: Descriptive string for the lookback period.

    Returns:
        Number of edges written.
    """
    written = 0
    for label_a, label_b, coeff in high_pairs:
        champ_a = champion_map[label_a]
        champ_b = champion_map[label_b]
        try:
            store.write_correlated_with(
                champion_id_a=champ_a["champion_id"],
                strategy_id_a=champ_a["strategy_id"],
                champion_id_b=champ_b["champion_id"],
                strategy_id_b=champ_b["strategy_id"],
                coefficient=coeff,
                threshold=threshold,
                lookback=lookback,
            )
            written += 1
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"failed to write CORRELATED_WITH for {label_a}↔{label_b}: {exc}",
                stacklevel=2,
            )
    return written


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _label(champ: dict[str, Any]) -> str:
    """Short display label for a champion row."""
    return str(champ.get("strategy_id", champ.get("champion_id", "unknown")))


def print_report(
    labels: list[str],
    corr_matrix: pd.DataFrame,
    high_pairs: list[tuple[str, str, float]],
    threshold: float,
    champion_count: int,
    skipped: int,
) -> None:
    """Print formatted correlation report to stdout."""
    print(f"\nPortfolio Correlation Report ({champion_count} champions, {skipped} skipped)")
    print("─" * 60)

    if corr_matrix.empty:
        print("No series available for correlation — all champions skipped.")
        return

    if len(labels) < 2:
        print("Only one series available — pairwise correlation requires ≥ 2.")
        return

    # Abbreviated column headers
    short = {lbl: lbl[:12] for lbl in labels}
    header = "".ljust(20) + "".join(v.ljust(14) for v in short.values())
    print(header)
    for row_lbl in labels:
        row = short[row_lbl].ljust(20)
        for col_lbl in labels:
            val = corr_matrix.loc[row_lbl, col_lbl]
            marker = "*" if row_lbl != col_lbl and abs(val) > threshold else " "
            row += f"{val:.2f}{marker}".ljust(14)
        print(row)

    if high_pairs:
        print(f"\n* HIGH CORRELATION (|r| > {threshold:.2f}) — concentration risk")
        for a, b, r in high_pairs:
            print(f"  {a} ↔ {b}: r={r:.2f}  [review before running together]")
    else:
        print(f"\nNo pairs exceed threshold {threshold:.2f}.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    threshold: float = DEFAULT_THRESHOLD,
    repo_root: Path | None = None,
    store: Any | None = None,
    write_edges: bool = True,
) -> int:
    """Execute portfolio correlation analysis.

    Returns:
        0 on success, 1 on fatal error.
    """
    root = repo_root or Path.cwd()

    # Fetch OOS-pass champions from graph (or empty list when store unavailable)
    champions: list[dict[str, Any]] = []
    if store is not None:
        try:
            champions = store.get_portfolio_alpha_champions()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"graph unavailable: {exc} — running offline", stacklevel=2)

    if not champions:
        print("No OOS-pass champions found. Nothing to correlate.")
        return 0

    series_map: dict[str, pd.Series] = {}
    champion_map: dict[str, dict[str, Any]] = {}
    skipped = 0

    for champ in champions:
        artifact_path = champ.get("artifact_path")
        if not artifact_path:
            skipped += 1
            warnings.warn(
                f"champion {champ.get('champion_id')} has no artifact_path — skipping",
                stacklevel=2,
            )
            continue

        series = load_pnl_series(str(artifact_path), root)
        if series is None:
            skipped += 1
            continue

        lbl = _label(champ)
        series_map[lbl] = series
        champion_map[lbl] = champ

    if not series_map:
        print(f"All {len(champions)} champion(s) skipped (no usable P&L series).")
        return 0

    corr_matrix = compute_correlation_matrix(series_map)
    labels = list(series_map.keys())
    high_pairs = flag_high_pairs(corr_matrix, threshold)

    print_report(labels, corr_matrix, high_pairs, threshold, len(champions), skipped)

    if write_edges and store is not None and high_pairs:
        n = write_correlated_with_edges(store, champion_map, high_pairs, threshold)
        print(f"\nWrote {n} CORRELATED_WITH edge(s) to graph.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="portfolio_correlation",
        description="Compute pairwise correlation across OOS-pass Champions.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Correlation threshold for flagging pairs (default {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        default=False,
        help="Skip writing CORRELATED_WITH edges to graph",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root path (defaults to cwd)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    write_edges = not args.no_write

    # Attempt graph connection
    store_instance = None
    try:
        from qws_graph.research.graph.store import GraphStore  # noqa: PLC0415

        store_instance = GraphStore.from_env()
        store_instance.ping()
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"graph unavailable: {exc} — running offline", stacklevel=2)
        store_instance = None

    return run(
        threshold=args.threshold,
        repo_root=repo_root,
        store=store_instance,
        write_edges=write_edges,
    )


if __name__ == "__main__":
    sys.exit(main())
