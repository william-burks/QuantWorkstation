"""Fixture strategy script for unit tests.

Represents a production-grade trial script. Used to compute a realistic
family_id via source_hash — tests that pass a trivial stub would not catch
regressions in content-sensitive hashing logic.

Self-contained (no live data imports) so it can be read as bytes by tests
without touching the data store or any external dependency.
"""

from __future__ import annotations

CONFIG_OVERRIDES = {
    "target_r": 1.25,
    "max_hold_bars": 24,
    "wick_mode": "exclude_q2",
    "chain_mode": "no_smt_in_chain",
    "partial_exit_r": 0.0,
    "stall_bars": 0,
    "allowed_sessions": ["NY_PRE", "AFTER"],
    "allowed_dir": ["BEAR"],
}

INSTRUMENT = "CL"
TIMEFRAME = "1H"
DIRECTION = "bear"
LOGIC_TYPE = "liquidity-sweep"


def generate_signals(data):
    """Stub signal generator — not callable in tests."""
    raise NotImplementedError("fixture only — wire to real adapter for production use")


def main() -> None:
    raise NotImplementedError("fixture only — not executable")


if __name__ == "__main__":
    main()
