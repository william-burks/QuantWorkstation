"""Semantic analyst for grid-sweep candidate evaluation.

This module provides a thin OpenAI client wrapper for batch evaluation of
grid-sweep runs. Curation runs by default for all grid_csv ingests when
OPENAI_API_KEY is set. Pass --no-analyze to qw record to skip curation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import ResearchArtifact, Run, Strategy


class AnalystUnavailableError(RuntimeError):
    """Raised when the AI analyst is unreachable or unconfigured."""


@dataclass(frozen=True)
class AnnotationResult:
    """Result of LLM evaluation for a single run."""

    run_id: str
    approved: bool
    curator_note: str


class AnalystClient(Protocol):
    """Minimal analyst client interface used by CLI orchestration."""

    def annotate(self, artifact: ResearchArtifact) -> ResearchArtifact:
        """Return artifact with run-level semantic annotations."""


class OpenAIAnalyst:
    """Thin OpenAI API wrapper for grid-sweep semantic evaluation."""

    def __init__(
        self,
        api_key: str,
        model_id: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        """Initialize analyst with API key and model config.

        Args:
            api_key: OpenAI API key.
            model_id: Model identifier (default gpt-4o-mini).
            temperature: Inference temperature for determinism (default 0.1).

        Raises:
            AnalystUnavailableError: If api_key is empty or None.
        """
        if not api_key:
            raise AnalystUnavailableError("OPENAI_API_KEY is not set")
        self._api_key = api_key
        self._model_id = model_id
        self._temperature = temperature

    @classmethod
    def from_env(cls) -> OpenAIAnalyst:
        """Create analyst from environment variables.

        Raises:
            AnalystUnavailableError: If OPENAI_API_KEY is not set.
        """
        api_key = os.getenv("OPENAI_API_KEY", "")
        model_id = os.getenv("QW_AI_ANALYST_MODEL", "gpt-4o-mini")
        if not api_key:
            raise AnalystUnavailableError("OPENAI_API_KEY is not set")
        return cls(api_key=api_key, model_id=model_id)

    def annotate(self, artifact: ResearchArtifact) -> ResearchArtifact:
        """Evaluate all runs in artifact and return an annotated copy.

        Each run's curator_note is set based on the LLM response.

        Args:
            artifact: ResearchArtifact with runs to evaluate.

        Returns:
            New artifact with curator_note set on each run.

        Raises:
            AnalystUnavailableError: If the OpenAI API is unreachable.
        """
        if not artifact.runs:
            return artifact

        annotations = self._batch_annotate(artifact.strategy, artifact.runs)

        updated_runs = []
        for run in artifact.runs:
            if run.run_id in annotations:
                result = annotations[run.run_id]
                if result.approved:
                    updated_runs.append(
                        run.model_copy(
                            update={"curator_note": truncate_curator_note(result.curator_note)}
                        )
                    )
                else:
                    updated_runs.append(run.model_copy(update={"curator_note": None}))
            else:
                updated_runs.append(run)

        return artifact.model_copy(update={"runs": updated_runs})

    def _batch_annotate(self, strategy: Strategy, runs: list[Run]) -> dict[str, AnnotationResult]:
        """Evaluate runs in batch and return annotation results.

        Args:
            strategy: Strategy definition for context.
            runs: List of runs to evaluate.

        Returns:
            Dictionary mapping run_id to AnnotationResult.

        Raises:
            AnalystUnavailableError: If the OpenAI API is unreachable or returns an error.
        """
        try:
            import urllib.request
        except ImportError as exc:
            raise AnalystUnavailableError(f"Failed to import urllib: {exc}") from exc

        prompt = self._build_prompt(strategy, runs)

        try:
            request = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(
                    {
                        "model": self._model_id,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": self._temperature,
                    }
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
            raise AnalystUnavailableError(f"Failed to reach OpenAI API: {exc}") from exc

        try:
            message = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AnalystUnavailableError(f"Unexpected response format from OpenAI: {exc}") from exc

        return self._parse_response(message)

    def _build_prompt(self, strategy: Strategy, runs: list[Run]) -> str:
        """Construct the user prompt with compact CSV of run statistics."""
        rows = []
        for run in runs[:20]:
            rows.append(
                f"{run.run_id},{run.sharpe:.2f},{run.profit_factor:.2f},"
                f"{run.win_rate:.2f},{run.max_drawdown:.1f},{run.total_trades}"
            )

        csv_data = "\n".join(rows)
        return (
            f"Strategy: {strategy.strategy_id} | {strategy.logic_type} | {strategy.direction}\n"
            f"Candidates (run_id,sharpe,profit_factor,win_rate,max_drawdown,total_trades):\n"
            f"{csv_data}\n\n"
            f"For each run_id, return JSON array:\n"
            f'[{{"run_id": "...", "approved": true|false, "curator_note": "one sentence"}}]'
        )

    def _estimate_prompt_tokens(self, prompt: str) -> int:
        """Rough token estimator for prompt-size guardrails.

        Uses a conservative 4-char/token approximation suitable for acceptance checks.
        """
        return max(1, len(prompt) // 4)

    def _parse_response(self, message: str) -> dict[str, AnnotationResult]:
        """Parse LLM response and return annotation results.

        Defensive: handles partial/malformed responses gracefully.
        """
        try:
            parsed = json.loads(message)
            if not isinstance(parsed, list):
                return {}

            results = {}
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                run_id = item.get("run_id")
                if not run_id:
                    continue
                approved = item.get("approved", True)
                curator_note = item.get("curator_note", "")
                results[run_id] = AnnotationResult(
                    run_id=run_id,
                    approved=bool(approved),
                    curator_note=str(curator_note),
                )
            return results
        except json.JSONDecodeError:
            return {}


def truncate_curator_note(note: str | None, max_length: int = 280) -> str | None:
    """Cap curator notes to a stable max length for lean graph neighborhoods."""
    if note is None:
        return None
    return note[:max_length].strip()


class AnalystFactory:
    """Provider-based factory for semantic analyst clients.

    Supported providers:
    - ``openai`` (default): returns ``OpenAIAnalyst``
    """

    @staticmethod
    def from_env() -> AnalystClient:
        provider = os.getenv("QW_AI_PROVIDER", "openai").strip().lower()
        if provider == "openai":
            return OpenAIAnalyst.from_env()
        raise AnalystUnavailableError(f"Unsupported QW_AI_PROVIDER: {provider!r}")


_SYSTEM_PROMPT = """You are a quantitative research analyst reviewing backtest results.
Evaluate each run and provide your assessment as a JSON array. For each run:
- approved: true if the run looks promising for further investigation, false otherwise
- curator_note: a single sentence explaining your assessment

Base your decision on Sharpe ratio, profit factor, win rate, drawdown, and trade count.
Be concise and analytical. Return ONLY valid JSON, no other text."""


__all__ = [
    "AnalystClient",
    "AnalystFactory",
    "OpenAIAnalyst",
    "AnalystUnavailableError",
    "AnnotationResult",
    "truncate_curator_note",
]
