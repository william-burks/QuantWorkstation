"""Unit tests for promotion candidate evaluation logic (QWS-0405)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import _evaluate_promotion_candidates
from research.graph.models import Provenance, Run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2026, 1, 1, tzinfo=UTC)
_PROVENANCE = Provenance(
    artifact_path="results/test.csv",
    artifact_hash="abc123",
    artifact_mtime_iso="2026-01-01T00:00:00Z",
    ingested_at=_TS,
)


def _run(
    run_id: str = "aabbccddeeff",
    sharpe: float = 2.3,
    profit_factor: float = 2.1,
    win_rate: float = 0.66,
    total_trades: int = 45,
    active_window_frequency: float | None = 0.10,
    max_drawdown: float = -0.08,
) -> Run:
    return Run(
        run_id=run_id,
        strategy_id="es-1h-bear-sweep",
        timestamp=_TS,
        sharpe=sharpe,
        profit_factor=profit_factor,
        win_rate=win_rate,
        max_drawdown=max_drawdown,
        total_trades=total_trades,
        active_window_frequency=active_window_frequency,
        first_trade_ts=_TS,
        last_trade_ts=_TS,
        artifact_path="results/test.csv",
        provenance=_PROVENANCE,
    )


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------


class TestPromotionCandidateEvaluation:
    def test_qualifying_run_produces_alert(self):
        """AC1: sharpe=2.3, pf=2.1, drawdown=-0.08, trades=45, awf=0.10 → alert printed."""
        run = _run(run_id="aabbccddeeff")
        alerts = _evaluate_promotion_candidates([run], {"aabbccddeeff"})
        assert len(alerts) == 1
        assert "[PROMOTION CANDIDATE]" in alerts[0]
        assert "run_id=aabbccddeeff" in alerts[0]

    def test_low_sharpe_produces_no_alert(self):
        """AC2: sharpe=0.9 (below professional 1.5) → no alert."""
        run = _run(run_id="lowsharpe0001", sharpe=0.9)
        alerts = _evaluate_promotion_candidates([run], {"lowsharpe0001"})
        assert alerts == []

    def test_low_awf_produces_no_alert(self):
        """AC3: awf=0.03 (below 0.06 floor), otherwise passing → no alert."""
        run = _run(run_id="lowawf0000001", active_window_frequency=0.03)
        alerts = _evaluate_promotion_candidates([run], {"lowawf0000001"})
        assert alerts == []

    def test_null_awf_produces_no_alert(self):
        """AC4: awf=None (legacy run) → silently excluded, no alert."""
        run = _run(run_id="nullawf000001", active_window_frequency=None)
        alerts = _evaluate_promotion_candidates([run], {"nullawf000001"})
        assert alerts == []

    def test_skipped_run_produces_no_alert(self):
        """AC5: run_id not in persisted_run_ids (skipped) → no alert."""
        run = _run(run_id="skippedrun001")
        # persisted_run_ids is empty → this run was skipped
        alerts = _evaluate_promotion_candidates([run], set())
        assert alerts == []

    def test_low_trades_produces_no_alert(self):
        """Boundary: total_trades < 30 → no alert even with strong metrics."""
        run = _run(run_id="fewtrades0001", total_trades=29)
        alerts = _evaluate_promotion_candidates([run], {"fewtrades0001"})
        assert alerts == []

    def test_low_profit_factor_produces_no_alert(self):
        """Boundary: profit_factor below professional threshold → no alert."""
        run = _run(run_id="lowpf000000001", profit_factor=1.5)
        alerts = _evaluate_promotion_candidates([run], {"lowpf000000001"})
        assert alerts == []

    def test_institutional_tier_shown_when_both_metrics_qualify(self):
        """Runs clearing both sharpe>=2.5 and pf>=3.0 are labelled institutional."""
        run = _run(run_id="institutional01", sharpe=2.6, profit_factor=3.1)
        alerts = _evaluate_promotion_candidates([run], {"institutional01"})
        assert len(alerts) == 1
        assert "tier=institutional" in alerts[0]

    def test_professional_tier_shown_for_borderline_run(self):
        """Runs clearing professional but not institutional thresholds → tier=professional."""
        run = _run(run_id="professional01", sharpe=2.3, profit_factor=2.1)
        alerts = _evaluate_promotion_candidates([run], {"professional01"})
        assert len(alerts) == 1
        assert "tier=professional" in alerts[0]

    def test_multiple_runs_only_qualifying_alerted(self):
        """Multiple runs: only the one passing all criteria appears in output."""
        passing = _run(run_id="passingrun001")
        failing = _run(run_id="failingrun001", sharpe=0.5)
        persisted = {"passingrun001", "failingrun001"}
        alerts = _evaluate_promotion_candidates([passing, failing], persisted)
        assert len(alerts) == 1
        assert "passingrun001" in alerts[0]

    def test_empty_runs_produces_no_alert(self):
        """No runs → no alerts."""
        alerts = _evaluate_promotion_candidates([], set())
        assert alerts == []