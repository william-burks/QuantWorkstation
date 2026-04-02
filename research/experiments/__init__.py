from research.experiments.evaluator import evaluate, report, worst_trades
from research.experiments.metrics import summary
from research.experiments.standards import CALMAR, MAX_DRAWDOWN_LIMIT, PROFIT_FACTOR, SHARPE, TIERS

try:
    from research.experiments.sweep import sweep
except ModuleNotFoundError:  # pragma: no cover - optional vectorbt dependency
    sweep = None

__all__ = [
    "evaluate",
    "report",
    "worst_trades",
    "summary",
    "sweep",
    "SHARPE",
    "PROFIT_FACTOR",
    "CALMAR",
    "MAX_DRAWDOWN_LIMIT",
    "TIERS",
]
