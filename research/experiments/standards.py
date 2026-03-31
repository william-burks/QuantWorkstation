"""
Centralized performance standards for strategy evaluation.

All thresholds are defined here — nowhere else. Importing these constants
ensures that tier boundaries are consistent across every trial and report.

Tier assignment uses the *lowest* metric tier across all three metrics.
A strategy passes only if ALL metrics are at or above the minimum thresholds.
"""

# --- Sharpe ratio thresholds (annualized) ---
SHARPE: dict[str, float] = {
    "pass": 0.8,
    "professional": 1.5,
    "institutional": 2.5,
}

# --- Profit factor thresholds (gross profit / gross loss) ---
PROFIT_FACTOR: dict[str, float] = {
    "pass": 1.3,
    "professional": 1.75,
    "institutional": 3.0,
}

# --- Calmar ratio thresholds (annual return / abs max drawdown) ---
CALMAR: dict[str, float] = {
    "pass": 1.5,
    "professional": 3.0,
    "institutional": 5.0,
}

# --- Hard limits — automatic FAIL regardless of other metrics ---
MAX_DRAWDOWN_LIMIT: float = -0.20   # DD worse than -20% = FAIL

# --- Statistical reliability floor ---
MIN_TRADES_PER_YEAR: int = 12       # Below this trade count = unreliable

# --- Tier ordering (best → worst) ---
TIERS: list[str] = ["institutional", "professional", "pass", "fail"]
