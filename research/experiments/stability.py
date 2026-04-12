"""
Parameter Stability Analysis

Given a champion run_id and a list of neighboring runs (from a grid sweep),
computes a stability score that measures whether the champion sits on a
broad performance plateau or an isolated peak.

HEURISTIC DISCLAIMER
--------------------
The stability score `1 - (σ / μ)` is a coefficient of variation inversion.
It is NOT a statistical test. It does not account for:
  - Correlation between neighboring runs (parameters may be co-varying)
  - Non-normality of Sharpe distributions
  - Multiple comparisons across the parameter grid
Use it as a screening heuristic to flag candidates for manual review,
not as a pass/fail gate.

Assumptions:
  - "Neighbors" are defined by L∞ distance (max absolute difference per
    normalized parameter dimension) within a caller-supplied threshold.
  - Parameters are normalized to [0, 1] per dimension before distance
    calculation, so differently-scaled parameters have equal weight.
  - Sharpe values are taken at face value (IS Sharpe from grid CSV).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RunRecord:
    """Minimal representation of a grid-sweep row."""

    run_id: str
    sharpe: float
    params: dict[str, float]


@dataclass
class StabilityResult:
    """Output of compute_stability()."""

    run_id: str
    champion_sharpe: float
    neighbor_count: int
    neighbor_sharpe_mean: float
    neighbor_sharpe_std: float
    stability_score: float  # 1 - (σ/μ), clamped [0, 1]; -1.0 = insufficient data
    assessment: str  # ROBUST | MODERATE | BRITTLE | INSUFFICIENT_DATA
    nearest_failing_neighbor: RunRecord | None = field(default=None)

    def __str__(self) -> str:
        if self.assessment == "INSUFFICIENT_DATA":
            return (
                f"Parameter Stability Report: run_id={self.run_id}\n"
                f"  INSUFFICIENT DATA — no neighboring runs found within threshold\n"
                f"  Cannot assess stability without grid sweep neighbors."
            )
        parts = [
            f"Parameter Stability Report: run_id={self.run_id}",
            f"  Champion sharpe:     {self.champion_sharpe:.2f}",
            f"  Neighbors found:     {self.neighbor_count} runs",
            f"  Neighbor sharpe μ:   {self.neighbor_sharpe_mean:.2f}",
            f"  Neighbor sharpe σ:   {self.neighbor_sharpe_std:.2f}",
            f"  Stability score:     {self.stability_score:.2f}  (1.0 = perfectly stable plateau)",
            f"  Assessment:          {_assessment_label(self.assessment)}",
        ]
        if self.nearest_failing_neighbor is not None:
            nfn = self.nearest_failing_neighbor
            parts.append(
                f"\n  Nearest failing neighbor: run_id={nfn.run_id}, sharpe={nfn.sharpe:.2f}"
            )
        return "\n".join(parts)


def _assessment_label(code: str) -> str:
    labels = {
        "ROBUST": "ROBUST — champion sits on a broad performance plateau",
        "MODERATE": "MODERATE — some instability around champion parameters",
        "BRITTLE": "BRITTLE — champion is likely an isolated peak",
        "INSUFFICIENT_DATA": "INSUFFICIENT DATA",
    }
    return labels.get(code, code)


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def _normalize_params(runs: list[RunRecord], param_keys: list[str]) -> list[RunRecord]:
    """
    Return new RunRecords with params normalized per-dimension to [0, 1].
    Dimensions with zero range are left as-is (all values equal → distance = 0).
    """
    if not runs or not param_keys:
        return runs

    df = pd.DataFrame([r.params for r in runs], index=[r.run_id for r in runs])
    for col in param_keys:
        lo, hi = df[col].min(), df[col].max()
        if hi > lo:
            df[col] = (df[col] - lo) / (hi - lo)
        else:
            df[col] = 0.0  # constant dimension — contributes 0 distance

    return [
        RunRecord(run_id=r.run_id, sharpe=r.sharpe, params=dict(df.loc[r.run_id])) for r in runs
    ]


def _param_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """L∞ (Chebyshev) distance between two normalized parameter dicts."""
    keys = set(a) & set(b)
    if not keys:
        return float("inf")
    return max(abs(a[k] - b[k]) for k in keys)


def find_neighbors(
    champion: RunRecord,
    all_runs: list[RunRecord],
    threshold: float = 0.2,
) -> list[RunRecord]:
    """
    Return runs within L∞ distance `threshold` of `champion` in normalized
    parameter space. Excludes the champion itself.

    Parameters
    ----------
    champion : RunRecord
        The reference run.
    all_runs : list[RunRecord]
        Full grid, including champion.
    threshold : float
        Max per-dimension normalized distance to qualify as a neighbor.
        Default 0.2 = 20% of each parameter's range.
    """
    param_keys = list(champion.params.keys())
    normalized = _normalize_params(all_runs, param_keys)

    # Locate normalized champion
    champ_norm = next(r for r in normalized if r.run_id == champion.run_id)

    neighbors = []
    for run in normalized:
        if run.run_id == champion.run_id:
            continue
        if _param_distance(run.params, champ_norm.params) <= threshold:
            neighbors.append(run)
    return neighbors


def compute_stability(
    champion: RunRecord,
    all_runs: list[RunRecord],
    threshold: float = 0.2,
    robust_cutoff: float = 0.7,
    brittle_cutoff: float = 0.4,
) -> StabilityResult:
    """
    Compute stability score for a champion run.

    Stability score = 1 - (σ_neighbors / μ_neighbors), clamped to [0, 1].
    Requires μ_neighbors > 0 to avoid division by zero.

    Parameters
    ----------
    champion : RunRecord
    all_runs : list[RunRecord]
        All grid runs including champion.
    threshold : float
        Neighbor distance threshold (normalized L∞). Default 0.2.
    robust_cutoff : float
        Score >= this → ROBUST. Default 0.7.
    brittle_cutoff : float
        Score < this → BRITTLE. Default 0.4.
    """
    neighbors = find_neighbors(champion, all_runs, threshold)

    if not neighbors:
        return StabilityResult(
            run_id=champion.run_id,
            champion_sharpe=champion.sharpe,
            neighbor_count=0,
            neighbor_sharpe_mean=float("nan"),
            neighbor_sharpe_std=float("nan"),
            stability_score=-1.0,
            assessment="INSUFFICIENT_DATA",
        )

    sharpes = np.array([r.sharpe for r in neighbors])
    mu = float(sharpes.mean())
    sigma = float(sharpes.std(ddof=0))  # population std — small sample, no ddof

    if mu <= 0:
        # Negative mean sharpe neighborhood — score = 0 by convention
        score = 0.0
    else:
        raw = 1.0 - (sigma / mu)
        score = float(np.clip(raw, 0.0, 1.0))

    if score >= robust_cutoff:
        assessment = "ROBUST"
    elif score < brittle_cutoff:
        assessment = "BRITTLE"
    else:
        assessment = "MODERATE"

    # Nearest failing neighbor (sharpe < 0)
    failing = [r for r in neighbors if r.sharpe < 0]
    nearest_failing: RunRecord | None = None
    if failing:
        param_keys = list(champion.params.keys())
        normalized = _normalize_params(all_runs, param_keys)
        champ_norm = next(r for r in normalized if r.run_id == champion.run_id)
        norm_map = {r.run_id: r for r in normalized}
        nearest_failing = min(
            failing,
            key=lambda r: _param_distance(norm_map[r.run_id].params, champ_norm.params),
        )

    return StabilityResult(
        run_id=champion.run_id,
        champion_sharpe=champion.sharpe,
        neighbor_count=len(neighbors),
        neighbor_sharpe_mean=mu,
        neighbor_sharpe_std=sigma,
        stability_score=score,
        assessment=assessment,
        nearest_failing_neighbor=nearest_failing,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_mock_runs_from_graph(run_id: str) -> tuple[RunRecord, list[RunRecord]]:  # noqa: ARG001
    """
    Placeholder: in a live environment this would call:
      qw query --name run_history --param strategy_id=<sid>
    and parse params_json from each run's Config node.

    Returns (champion, all_runs). Raises RuntimeError if run_id not found.
    This stub always raises — real data requires a live Neo4j connection.
    """
    raise RuntimeError(
        f"No live graph connection. run_id={run_id} cannot be resolved.\n"
        "To use stability analysis against real data, call compute_stability() "
        "directly from a script with RunRecord objects populated from qw query output."
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Parameter stability analysis for a champion run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--run-id", required=True, help="Champion run_id to analyze")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="Neighbor distance threshold in normalized L∞ space (default: 0.2)",
    )
    args = parser.parse_args(argv)

    try:
        champion, all_runs = _build_mock_runs_from_graph(args.run_id)
        result = compute_stability(champion, all_runs, threshold=args.threshold)
        print(result)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
