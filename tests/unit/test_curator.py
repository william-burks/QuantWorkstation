"""Unit tests for research.graph.curator — apply_significance_gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from research.graph.curator import apply_significance_gate
from research.graph.models import Config, Provenance, ResearchArtifact, Run, Strategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROVENANCE = Provenance(
    artifact_path="results/grid.csv",
    artifact_hash="abc123",
    artifact_mtime_iso="2026-04-01T00:00:00Z",
    ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    parser_version="v1",
)

_STRATEGY = Strategy(
    strategy_id="es-1h-bear-sweep",
    instrument="ES",
    timeframe="1H",
    direction="bear",
    logic_type="MeanReversion",
)


def _make_run(run_id: str, sharpe: float, max_drawdown: float) -> Run:
    return Run(
        run_id=run_id,
        strategy_id="es-1h-bear-sweep",
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        sharpe=sharpe,
        profit_factor=1.2,
        win_rate=0.5,
        max_drawdown=max_drawdown,
        total_trades=100,
        first_trade_ts=datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC),
        last_trade_ts=datetime(2025, 10, 1, 16, 0, 0, tzinfo=UTC),
        artifact_path="results/grid.csv",
        provenance=_PROVENANCE,
    )


def _make_config(config_id: str) -> Config:
    return Config(config_id=config_id, params_json={}, risk_params={})


def _make_artifact(
    n: int, base_sharpe: float = 0.0, base_drawdown: float = -0.05
) -> ResearchArtifact:
    """Create a grid_csv artifact with *n* runs."""
    runs = [
        _make_run(f"run-{i:04d}", base_sharpe + i * 0.01, base_drawdown - i * 0.001)
        for i in range(n)
    ]
    configs = [_make_config(f"cfg-{i:04d}") for i in range(n)]
    return ResearchArtifact(kind="grid_csv", strategy=_STRATEGY, runs=runs, configs=configs)


# ---------------------------------------------------------------------------
# Gate application
# ---------------------------------------------------------------------------


class TestApplySignificanceGate:
    def test_rejects_non_grid_csv(self) -> None:
        artifact = _make_artifact(3)
        baseline = artifact.model_copy(update={"kind": "baseline_csv"})
        with pytest.raises(ValueError, match="grid_csv"):
            apply_significance_gate(baseline)

    def test_1000_row_artifact_produces_le_10_runs(self) -> None:
        artifact = _make_artifact(1000)
        selected, summary = apply_significance_gate(artifact)
        assert len(selected.runs) <= 10
        assert len(selected.runs) == len(selected.configs)

    def test_default_top5_sharpe_selected(self) -> None:
        artifact = _make_artifact(20)
        selected, _ = apply_significance_gate(artifact, top_n_sharpe=5, bottom_n_drawdown=0)
        # Highest sharpe runs are at the end (base_sharpe + i*0.01)
        selected_ids = {r.run_id for r in selected.runs}
        top5_ids = {f"run-{i:04d}" for i in range(15, 20)}
        assert top5_ids.issubset(selected_ids)

    def test_bottom2_drawdown_selected(self) -> None:
        # Worst drawdown (most negative) = highest index (base_drawdown - i*0.001)
        artifact = _make_artifact(20)
        selected, _ = apply_significance_gate(artifact, top_n_sharpe=0, bottom_n_drawdown=2)
        selected_ids = {r.run_id for r in selected.runs}
        worst2_ids = {"run-0018", "run-0019"}
        assert worst2_ids.issubset(selected_ids)

    def test_pinned_run_ids_always_included(self) -> None:
        artifact = _make_artifact(20)
        pinned = {"run-0000", "run-0010"}
        selected, _ = apply_significance_gate(artifact, pinned_run_ids=pinned)
        selected_ids = {r.run_id for r in selected.runs}
        assert pinned.issubset(selected_ids)

    def test_selection_is_non_overlapping(self) -> None:
        artifact = _make_artifact(100)
        selected, summary = apply_significance_gate(artifact, top_n_sharpe=5, bottom_n_drawdown=2)
        run_ids = [r.run_id for r in selected.runs]
        assert len(run_ids) == len(set(run_ids)), "Selected runs must be unique"

    def test_runs_and_configs_remain_paired(self) -> None:
        artifact = _make_artifact(50)
        selected, _ = apply_significance_gate(artifact)
        assert len(selected.runs) == len(selected.configs)
        for run, config in zip(selected.runs, selected.configs, strict=True):
            # run index matches config index: run-NNNN → cfg-NNNN
            assert run.run_id.split("-")[1] == config.config_id.split("-")[1]

    def test_small_artifact_under_threshold_keeps_all(self) -> None:
        artifact = _make_artifact(3)
        selected, summary = apply_significance_gate(artifact, top_n_sharpe=5, bottom_n_drawdown=2)
        assert len(selected.runs) == 3
        assert summary.rolled_up_run_count == 0

    def test_summary_total_count_matches_original(self) -> None:
        artifact = _make_artifact(100)
        selected, summary = apply_significance_gate(artifact)
        assert summary.total_run_count == 100

    def test_summary_selected_plus_rolled_up_equals_total(self) -> None:
        artifact = _make_artifact(100)
        selected, summary = apply_significance_gate(artifact)
        assert summary.selected_run_count + summary.rolled_up_run_count == summary.total_run_count

    def test_summary_strategy_id_matches_artifact(self) -> None:
        artifact = _make_artifact(10)
        _, summary = apply_significance_gate(artifact)
        assert summary.strategy_id == artifact.strategy.strategy_id

    def test_summary_sharpe_stats_cover_all_runs(self) -> None:
        artifact = _make_artifact(20)
        _, summary = apply_significance_gate(artifact)
        all_sharpes = [r.sharpe for r in artifact.runs]
        assert abs(summary.sharpe_max - max(all_sharpes)) < 1e-9
        assert abs(summary.sharpe_min - min(all_sharpes)) < 1e-9

    def test_summary_max_drawdown_worst_is_most_negative(self) -> None:
        artifact = _make_artifact(20)
        _, summary = apply_significance_gate(artifact)
        all_dds = [r.max_drawdown for r in artifact.runs]
        assert abs(summary.max_drawdown_worst - min(all_dds)) < 1e-9

    def test_summary_id_is_deterministic(self) -> None:
        artifact = _make_artifact(10)
        _, s1 = apply_significance_gate(artifact)
        _, s2 = apply_significance_gate(artifact)
        assert s1.summary_id == s2.summary_id

    def test_original_artifact_is_not_mutated(self) -> None:
        artifact = _make_artifact(100)
        original_count = len(artifact.runs)
        apply_significance_gate(artifact)
        assert len(artifact.runs) == original_count


# ---------------------------------------------------------------------------
# --all bypass (pass-through)
# ---------------------------------------------------------------------------


class TestAllPassthrough:
    def test_all_rows_pass_through_when_top_n_exceeds_count(self) -> None:
        artifact = _make_artifact(5)
        selected, summary = apply_significance_gate(
            artifact, top_n_sharpe=100, bottom_n_drawdown=100
        )
        assert len(selected.runs) == 5
        assert summary.selected_run_count == 5
        assert summary.rolled_up_run_count == 0
