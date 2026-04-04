"""Significance gate for grid-sweep artifact ingestion.

The Curator is a pure-function layer that sits between ``CSVParser.parse()``
and ``GraphStore.persist_artifact()``.  It reduces a full grid-sweep
``ResearchArtifact`` to the instructive subset of runs and produces a
``RunStatsSummary`` aggregate for the remainder.

Selection tiers (applied in order, non-overlapping):

1. **Performance** — Top N rows by ``sharpe`` (default 5).
2. **Risk boundary** — Bottom N rows by ``max_drawdown`` among unselected rows
   (most negative / lowest value = worst drawdown, default 2).
3. **Provenance pins** — Any run whose ``run_id`` is in ``pinned_run_ids``.

``baseline_csv`` artifacts are never filtered — pass them through unchanged.
The gate applies only to ``grid_csv``.

Reference: ``docs/graph_v1_contract.md`` — § Ingestion / Significance Gate
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .ids import run_stats_summary_id

if TYPE_CHECKING:
    from .models import ResearchArtifact, RunStatsSummary


def apply_significance_gate(
    artifact: "ResearchArtifact",
    top_n_sharpe: int = 5,
    bottom_n_drawdown: int = 2,
    pinned_run_ids: set[str] | None = None,
) -> "tuple[ResearchArtifact, RunStatsSummary]":
    """Apply the significance gate to a ``grid_csv`` artifact.

    Args:
        artifact:         Fully parsed ``ResearchArtifact`` with kind ``grid_csv``.
        top_n_sharpe:     Number of top-performing runs to keep (by ``sharpe``).
        bottom_n_drawdown: Number of worst-drawdown runs to keep (from remaining).
        pinned_run_ids:   Run IDs that must always be included (e.g. pivot runs).

    Returns:
        ``(selected, summary)`` where *selected* contains only the instructive
        runs and *summary* holds aggregate stats for the full original run set.

    Raises:
        ValueError: If ``artifact.kind`` is not ``grid_csv``.
    """
    from .models import RunStatsSummary

    if artifact.kind != "grid_csv":
        raise ValueError(
            f"apply_significance_gate only accepts grid_csv artifacts, got {artifact.kind!r}"
        )

    pairs: list[tuple] = list(zip(artifact.runs, artifact.configs, strict=True))
    n = len(pairs)
    pinned = pinned_run_ids or set()

    # ── aggregate stats across ALL runs ──────────────────────────────────────
    all_sharpes = [r.sharpe for r, _ in pairs]
    all_drawdowns = [r.max_drawdown for r, _ in pairs]

    sharpe_mean = sum(all_sharpes) / n if n > 0 else 0.0
    sharpe_max = max(all_sharpes) if all_sharpes else 0.0
    sharpe_min = min(all_sharpes) if all_sharpes else 0.0
    max_drawdown_worst = min(all_drawdowns) if all_drawdowns else 0.0  # most negative

    # ── selection ─────────────────────────────────────────────────────────────
    selected: set[int] = set()

    # Tier 1: top-N sharpe
    by_sharpe = sorted(range(n), key=lambda i: pairs[i][0].sharpe, reverse=True)
    for i in by_sharpe[:top_n_sharpe]:
        selected.add(i)

    # Tier 2: bottom-N drawdown (worst = lowest value) from remaining
    remaining = [i for i in range(n) if i not in selected]
    by_drawdown = sorted(remaining, key=lambda i: pairs[i][0].max_drawdown)
    for i in by_drawdown[:bottom_n_drawdown]:
        selected.add(i)

    # Tier 3: provenance pins
    for i, (run, _) in enumerate(pairs):
        if run.run_id in pinned:
            selected.add(i)

    selected_pairs = [pairs[i] for i in sorted(selected)]
    selected_runs = [r for r, _ in selected_pairs]
    selected_configs = [c for _, c in selected_pairs]

    selected_artifact = artifact.model_copy(
        update={"runs": selected_runs, "configs": selected_configs}
    )

    # ── summary node ──────────────────────────────────────────────────────────
    first_run = artifact.runs[0]
    summary = RunStatsSummary(
        summary_id=run_stats_summary_id(
            artifact.strategy.strategy_id,
            first_run.artifact_path,
            first_run.provenance.artifact_mtime_iso,
        ),
        strategy_id=artifact.strategy.strategy_id,
        artifact_path=first_run.artifact_path,
        total_run_count=n,
        selected_run_count=len(selected_runs),
        rolled_up_run_count=n - len(selected_runs),
        sharpe_mean=sharpe_mean,
        sharpe_max=sharpe_max,
        sharpe_min=sharpe_min,
        max_drawdown_worst=max_drawdown_worst,
        ingested_at=datetime.now(UTC),
    )

    return selected_artifact, summary


__all__ = ["apply_significance_gate"]
