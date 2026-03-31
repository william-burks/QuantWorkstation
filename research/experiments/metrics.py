"""
Performance metrics for strategy evaluation.

All functions accept an equity curve as a pd.Series (DatetimeIndex, float values)
or a returns Series (pct change of equity). Functions are intentionally stateless
and composable — call them individually or via summary().
"""

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


def returns(equity: pd.Series) -> pd.Series:
    """Percentage returns from equity curve."""
    return equity.pct_change().dropna()


def sharpe(equity: pd.Series, risk_free: float = 0.0) -> float:
    """Annualised Sharpe ratio."""
    r = returns(equity)
    if r.std() == 0:
        return 0.0
    return float((r.mean() - risk_free / _TRADING_DAYS) / r.std() * np.sqrt(_TRADING_DAYS))


def max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown as a negative fraction (e.g. -0.15 = 15% drawdown)."""
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def calmar(equity: pd.Series) -> float:
    """Calmar ratio: annualised return / abs(max drawdown)."""
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return 0.0
    r = returns(equity)
    annual_return = float(r.mean() * _TRADING_DAYS)
    return annual_return / mdd


def win_rate(pnl: pd.Series) -> float:
    """
    Fraction of profitable trades.
    pnl: Series of per-trade P&L values (not equity curve).
    """
    if len(pnl) == 0:
        return 0.0
    return float((pnl > 0).sum() / len(pnl))


def profit_factor(pnl: pd.Series) -> float:
    """Gross profit / gross loss. Returns inf if no losing trades."""
    gross_profit = pnl[pnl > 0].sum()
    gross_loss = abs(pnl[pnl < 0].sum())
    if gross_loss == 0:
        return float("inf")
    return float(gross_profit / gross_loss)


def summary(equity: pd.Series, pnl: pd.Series | None = None) -> dict:
    """
    Full performance summary.

    Parameters
    ----------
    equity : pd.Series
        Equity curve (account value over time).
    pnl : pd.Series, optional
        Per-trade P&L for win rate and profit factor.
        If None, win_rate and profit_factor are omitted.
    """
    r = returns(equity)
    result = {
        "return": float((equity.iloc[-1] / equity.iloc[0]) - 1),
        "annual_return": float(r.mean() * _TRADING_DAYS),
        "annual_volatility": float(r.std() * np.sqrt(_TRADING_DAYS)),
        "sharpe": sharpe(equity),
        "calmar": calmar(equity),
        "max_drawdown": max_drawdown(equity),
        "n_bars": len(equity),
    }
    if pnl is not None:
        result["win_rate"] = win_rate(pnl)
        result["profit_factor"] = profit_factor(pnl)
    return result
