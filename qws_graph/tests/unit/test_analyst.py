"""Unit tests for semantic analyst (Story: OpenAI Curation Switch QWS-0703)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

analyst_module = import_module("research.graph.analyst")
models_module = import_module("research.graph.models")

OpenAIAnalyst = analyst_module.OpenAIAnalyst
AnalystUnavailableError = analyst_module.AnalystUnavailableError
AnnotationResult = analyst_module.AnnotationResult
AnalystFactory = analyst_module.AnalystFactory

Config = models_module.Config
Provenance = models_module.Provenance
ResearchArtifact = models_module.ResearchArtifact
Run = models_module.Run
Strategy = models_module.Strategy


def _fixed_provenance() -> Provenance:
    return Provenance(
        artifact_path="results/test.csv",
        artifact_hash="abc123",
        artifact_mtime_iso="2026-04-02T12:30:00Z",
        ingested_at=datetime(2026, 4, 2, 12, 30, tzinfo=UTC),
    )


def _test_strategy() -> Strategy:
    return Strategy(
        strategy_id="es-1h-bear-sweep",
        instrument="ES",
        timeframe="1H",
        direction="bear",
        logic_type="sweep",
    )


def _test_run(idx: int, sharpe: float = 1.2) -> Run:
    return Run(
        run_id=f"run-{idx:03d}",
        strategy_id="es-1h-bear-sweep",
        timestamp=datetime(2026, 4, 2, 12, 0, tzinfo=UTC),
        sharpe=sharpe,
        profit_factor=1.1,
        win_rate=0.4,
        max_drawdown=-7.0,
        total_trades=40 + idx,
        first_trade_ts=datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC),
        last_trade_ts=datetime(2025, 10, 1, 16, 0, 0, tzinfo=UTC),
        artifact_path="results/test.csv",
        curator_note=None,
        provenance=_fixed_provenance(),
    )


def _test_config(idx: int) -> Config:
    return Config(
        config_id=f"cfg-{idx:03d}",
        params_json={"target_r": 1.5},
        risk_params={"atr_mult_stop": 0.5},
    )


def _test_artifact(runs_count: int = 3) -> ResearchArtifact:
    runs = [_test_run(i, sharpe=1.3 - i * 0.1) for i in range(runs_count)]
    configs = [_test_config(i) for i in range(runs_count)]
    return ResearchArtifact(
        kind="grid_csv",
        strategy=_test_strategy(),
        runs=runs,
        configs=configs,
    )


class TestOpenAIAnalystInitialization:
    def test_from_env_with_api_key_set(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            analyst = OpenAIAnalyst.from_env()
            assert analyst._api_key == "sk-test-key"

    def test_from_env_without_api_key_raises_unavailable(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AnalystUnavailableError, match="OPENAI_API_KEY is not set"):
                OpenAIAnalyst.from_env()

    def test_direct_init_with_empty_key_raises(self) -> None:
        with pytest.raises(AnalystUnavailableError, match="OPENAI_API_KEY is not set"):
            OpenAIAnalyst(api_key="")

    def test_from_env_reads_model_env_var(self) -> None:
        env = {"OPENAI_API_KEY": "sk-test", "QW_AI_ANALYST_MODEL": "gpt-4o"}
        with patch.dict("os.environ", env):
            analyst = OpenAIAnalyst.from_env()
            assert analyst._model_id == "gpt-4o"

    def test_from_env_defaults_to_gpt4o_mini(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            analyst = OpenAIAnalyst.from_env()
            assert analyst._model_id == "gpt-4o-mini"


class TestAnalystFactory:
    def test_factory_returns_openai_client_by_default(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = AnalystFactory.from_env()
            assert isinstance(client, OpenAIAnalyst)

    def test_factory_respects_provider_env(self) -> None:
        with patch.dict(
            "os.environ",
            {"QW_AI_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"},
            clear=True,
        ):
            client = AnalystFactory.from_env()
            assert isinstance(client, OpenAIAnalyst)

    def test_factory_rejects_unknown_provider(self) -> None:
        with patch.dict("os.environ", {"QW_AI_PROVIDER": "unknown"}, clear=True):
            with pytest.raises(AnalystUnavailableError, match="Unsupported QW_AI_PROVIDER"):
                AnalystFactory.from_env()


class TestOpenAIAnalystAnnotation:
    def test_annotate_empty_artifact_returns_unchanged(self) -> None:
        analyst = OpenAIAnalyst(api_key="sk-test")
        # Create a valid artifact first with at least one run
        artifact = _test_artifact(1)
        # Then override to empty for the test
        artifact = artifact.model_copy(update={"runs": [], "configs": []}, deep=True)
        result = analyst.annotate(artifact)
        assert result.runs == []

    @patch("urllib.request.urlopen")
    def test_annotate_batch_with_mock_llm(self, mock_urlopen) -> None:
        artifact = _test_artifact(3)
        analyst = OpenAIAnalyst(api_key="sk-test")

        # Mock OpenAI response — only approves first 2 of 3 runs
        mock_response = MagicMock()
        _runs = (
            '[{"run_id": "run-000", "approved": true, "curator_note": "Strong Sharpe ratio."},'
            ' {"run_id": "run-001", "approved": false, "curator_note": "High drawdown concern."}]'
        )
        mock_response.read.return_value = (
            '{"choices": [{"message": {"content": ' + __import__("json").dumps(_runs) + "}}]}"
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = analyst.annotate(artifact)

        # First run approved and has note, second unapproved so no note,
        # third not in response so no note
        assert result.runs[0].curator_note == "Strong Sharpe ratio."
        assert result.runs[1].curator_note is None
        # Third run not in LLM response, so no note set
        if len(result.runs) > 2:
            assert result.runs[2].curator_note is None

    @patch("urllib.request.urlopen")
    def test_annotate_defensive_parser_on_malformed_json(self, mock_urlopen) -> None:
        artifact = _test_artifact(2)
        analyst = OpenAIAnalyst(api_key="sk-test")

        # Mock response with malformed JSON
        mock_response = MagicMock()
        mock_response.read.return_value = b"""{
            "choices": [{
                "message": {
                    "content": "not valid json {{"
                }
            }]
        }"""
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = analyst.annotate(artifact)

        # Should return unchanged artifact on parse error
        assert all(r.curator_note is None for r in result.runs)

    @patch("urllib.request.urlopen")
    def test_annotate_with_endpoint_unreachable(self, mock_urlopen) -> None:
        artifact = _test_artifact(1)
        analyst = OpenAIAnalyst(api_key="sk-test")

        mock_urlopen.side_effect = OSError("Connection refused")

        with pytest.raises(AnalystUnavailableError, match="Failed to reach OpenAI API"):
            analyst.annotate(artifact)

    @patch("urllib.request.urlopen")
    def test_annotate_truncates_long_curator_notes(self, mock_urlopen) -> None:
        artifact = _test_artifact(1)
        analyst = OpenAIAnalyst(api_key="sk-test")

        long_note = "x" * 500
        _run_content = f'[{{"run_id": "run-000", "approved": true, "curator_note": "{long_note}"}}]'
        mock_response = MagicMock()
        mock_response.read.return_value = (
            '{"choices": [{"message": {"content": '
            + __import__("json").dumps(_run_content)
            + "}}]}"
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = analyst.annotate(artifact)

        # Note should be truncated to max 280 characters
        assert len(result.runs[0].curator_note) == 280
        assert result.runs[0].curator_note == "x" * 280

    @patch("urllib.request.urlopen")
    def test_request_includes_authorization_header(self, mock_urlopen) -> None:
        artifact = _test_artifact(1)
        analyst = OpenAIAnalyst(api_key="sk-testkey123")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "[]"}}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        analyst.annotate(artifact)

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer sk-testkey123"


class TestPromptConstruction:
    def test_build_prompt_includes_csv_rows(self) -> None:
        artifact = _test_artifact(3)
        analyst = OpenAIAnalyst(api_key="sk-test")

        prompt = analyst._build_prompt(artifact.strategy, artifact.runs)

        assert "es-1h-bear-sweep" in prompt
        assert "sweep" in prompt
        assert "bear" in prompt
        assert "run-000" in prompt
        assert "1.30" in prompt
        assert "Candidates" in prompt

    def test_prompt_token_estimate_under_2000_for_20_runs(self) -> None:
        artifact = _test_artifact(20)
        analyst = OpenAIAnalyst(api_key="sk-test")
        prompt = analyst._build_prompt(artifact.strategy, artifact.runs)
        assert analyst._estimate_prompt_tokens(prompt) < 2000


class TestAnnotationResult:
    def test_annotation_result_is_frozen(self) -> None:
        result = AnnotationResult(run_id="run-001", approved=True, curator_note="Good")
        with pytest.raises(AttributeError):
            result.approved = False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
