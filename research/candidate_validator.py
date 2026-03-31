"""
Validate a strategy candidate JSON against the handoff spec.

Usage:
    python research/candidate_validator.py <path/to/candidate.json>

Exit codes:
    0 — valid and meets all promotion criteria
    1 — validation failed (details printed to stdout)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator, model_validator
from pydantic import ValidationError

from research.experiments.standards import (
    CALMAR,
    MAX_DRAWDOWN_LIMIT,
    MIN_TRADES_PER_YEAR,
    PROFIT_FACTOR,
    SHARPE,
)


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------

class ParameterSpec(BaseModel):
    default: Any
    min: Any
    max: Any
    description: str = ""


class Timeframe(BaseModel):
    bar_size: str
    holding_period: str


class PreliminaryResults(BaseModel):
    sharpe: float
    max_drawdown: float
    win_rate: float
    n_trades: int | None = None
    notes: str = ""

    @field_validator("max_drawdown")
    @classmethod
    def drawdown_is_negative(cls, v: float) -> float:
        if v > 0:
            raise ValueError(f"max_drawdown must be negative or zero, got {v}")
        return v

    @field_validator("win_rate")
    @classmethod
    def win_rate_fraction(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"win_rate must be in [0, 1], got {v}")
        return v


class DateRange(BaseModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def is_iso_date(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"date must be YYYY-MM-DD, got {v!r}")
        return v


class DataUsed(BaseModel):
    symbols: list[str]
    date_range: DateRange
    bar_size: str = ""


class PaperReference(BaseModel):
    title: str
    authors: str
    year: int | None = None
    doi: str = ""
    url: str = ""
    notes: str = ""


class StrategyCandidate(BaseModel):
    candidate_id: str
    hypothesis: str
    signal_logic: str
    parameters: dict[str, ParameterSpec]
    asset_class: str
    contracts: list[str] = []
    timeframe: Timeframe
    preliminary_results: PreliminaryResults
    data_used: DataUsed
    paper_references: list[PaperReference]
    known_risks: list[str]
    researcher_notes: str

    @field_validator("candidate_id")
    @classmethod
    def valid_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+-\d{4}-\d{2}$", v):
            raise ValueError(
                f"candidate_id must match <concept>-YYYY-MM, got {v!r}"
            )
        return v

    @field_validator("asset_class")
    @classmethod
    def must_be_futures(cls, v: str) -> str:
        if v != "futures":
            raise ValueError(f"asset_class must be 'futures', got {v!r}")
        return v

    @model_validator(mode="after")
    def non_empty_required_strings(self) -> "StrategyCandidate":
        for field in ("hypothesis", "signal_logic", "researcher_notes"):
            if not getattr(self, field, "").strip():
                raise ValueError(f"{field} must not be empty")
        if not self.known_risks:
            raise ValueError("known_risks must contain at least one entry")
        if not self.paper_references:
            raise ValueError("paper_references must contain at least one entry")
        return self


# ---------------------------------------------------------------------------
# Promotion criteria check
# ---------------------------------------------------------------------------

def check_promotion(results: PreliminaryResults, n_years: float | None = None) -> list[str]:
    """Return a list of promotion failures. Empty list = passes all criteria."""
    failures: list[str] = []

    if results.sharpe < SHARPE["pass"]:
        failures.append(
            f"Sharpe {results.sharpe:.2f} < minimum {SHARPE['pass']}"
        )

    if results.max_drawdown < MAX_DRAWDOWN_LIMIT:
        failures.append(
            f"max_drawdown {results.max_drawdown:.1%} worse than limit {MAX_DRAWDOWN_LIMIT:.1%}"
        )

    # profit_factor and calmar are not in preliminary_results but warn if missing
    # (they require equity curve data; validator checks only what is present)

    if results.n_trades is not None:
        min_trades = MIN_TRADES_PER_YEAR * max(1, round(n_years or 1))
        if results.n_trades < min_trades:
            failures.append(
                f"n_trades {results.n_trades} < minimum {min_trades} "
                f"({MIN_TRADES_PER_YEAR}/yr × {max(1, round(n_years or 1))} yr)"
            )

    return failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(path: Path) -> tuple[bool, list[str]]:
    """Validate a candidate file. Returns (ok, list_of_errors)."""
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return False, [f"Could not read/parse file: {exc}"]

    try:
        candidate = StrategyCandidate.model_validate(raw)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return False, errors

    # Infer years from data_used date range for trade count check
    n_years: float | None = None
    try:
        from datetime import date
        start = date.fromisoformat(candidate.data_used.date_range.start)
        end = date.fromisoformat(candidate.data_used.date_range.end)
        n_years = (end - start).days / 365.25
    except ValueError:
        pass

    promo_failures = check_promotion(candidate.preliminary_results, n_years)
    if promo_failures:
        return False, promo_failures

    return True, []


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <candidate.json>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    ok, errors = validate(path)

    if ok:
        data = json.loads(path.read_text())
        print(f"PASS  {data.get('candidate_id', path.stem)}")
        sys.exit(0)
    else:
        print(f"FAIL  {path.name}")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()