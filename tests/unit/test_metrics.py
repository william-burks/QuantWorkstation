import numpy as np
import pandas as pd
import pytest

from research.experiments.metrics import (
    calmar,
    max_drawdown,
    profit_factor,
    sharpe,
    summary,
    win_rate,
)


def _equity(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="D"))


def test_sharpe_flat_returns_zero() -> None:
    eq = _equity([10_000.0] * 100)
    assert sharpe(eq) == 0.0


def test_sharpe_positive_trend() -> None:
    eq = _equity([10_000 + i * 10 for i in range(200)])
    assert sharpe(eq) > 0


def test_max_drawdown_no_drawdown() -> None:
    eq = _equity([10_000 + i for i in range(100)])
    assert max_drawdown(eq) == pytest.approx(0.0, abs=1e-6)


def test_max_drawdown_known_value() -> None:
    # Peak at 20k, drops to 10k → 50% drawdown
    eq = _equity([10_000, 15_000, 20_000, 10_000, 12_000])
    assert max_drawdown(eq) == pytest.approx(-0.5, abs=1e-6)


def test_calmar_positive() -> None:
    # Needs a drawdown to produce a non-zero calmar
    values = [10_000 + i * 5 for i in range(126)] + [10_000 + i * 10 for i in range(126)]
    eq = _equity(values)
    assert calmar(eq) > 0


def test_win_rate_all_winners() -> None:
    pnl = pd.Series([100.0, 200.0, 50.0])
    assert win_rate(pnl) == pytest.approx(1.0)


def test_win_rate_empty() -> None:
    assert win_rate(pd.Series([], dtype=float)) == 0.0


def test_profit_factor_no_losses() -> None:
    pnl = pd.Series([100.0, 200.0])
    assert profit_factor(pnl) == float("inf")


def test_profit_factor_known_value() -> None:
    pnl = pd.Series([200.0, -100.0])
    assert profit_factor(pnl) == pytest.approx(2.0)


def test_summary_keys() -> None:
    eq = _equity([10_000 + i * 10 for i in range(200)])
    pnl = pd.Series([50.0, -20.0, 80.0])
    result = summary(eq, pnl)
    for key in ("return", "sharpe", "calmar", "max_drawdown", "win_rate", "profit_factor"):
        assert key in result


def test_summary_without_pnl() -> None:
    eq = _equity([10_000 + i * 10 for i in range(200)])
    result = summary(eq)
    assert "win_rate" not in result
    assert "sharpe" in result
